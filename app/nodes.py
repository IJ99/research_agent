import os
import time
import re
from typing import List, Literal
from datetime import date
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from tavily import TavilyClient

from app.state import ResearchState

load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0, max_retries=6)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# The exact shape we want the LLM to return
# The exact shape we want the LLM to return
class SearchPlan(BaseModel):
    topic_type: Literal["timeless", "history", "current", "policy", "contested"] = Field(
        description="What kind of topic this is"
    )
    queries: List[str] = Field(description="3 focused, distinct web search queries")

SOURCE_BUDGET_CHARS = 8000   # total characters of source text per request


def format_sources(results, numbers=None):
    """Number the sources and share a fixed character budget between them.
    If `numbers` is given, include only those sources (keeping their original numbers)."""
    if numbers is None:
        numbers = list(range(1, len(results) + 1))
    per_source = max(300, min(1000, SOURCE_BUDGET_CHARS // max(len(numbers), 1)))
    return "\n\n".join(f"[{n}] {results[n - 1][:per_source]}" for n in numbers)

def planner_node(state: ResearchState) -> dict:
    topic = state["topic"]
    print(f"🧠 Planner: breaking down '{topic}'...")

    planner_llm = llm.with_structured_output(SearchPlan, method="json_schema").with_retry(stop_after_attempt=2)

    prompt = f"""You are a research planner. Today is {date.today()}.

STEP 1: Classify the topic as one of:
- "timeless": science, concepts, how things work (e.g. a law of physics)
- "history": past events (e.g. a war, a past repatriation)
- "current": an ongoing situation whose status changes (e.g. a vaccine rollout)
- "policy": a government or institutional policy and its effects
- "contested": a question where studies or experts disagree

STEP 2: Write exactly 3 search queries whose angles fit that type:
- timeless:  definition / how it works / examples or evidence
- history:   background / timeline of key events / outcome and aftermath
- current:   latest status / official figures / challenges
- policy:    what the policy says / how it was implemented / measured impact
- contested: evidence for / evidence against / reviews or meta-analyses

Rules:
- The 3 queries must cover DIFFERENT angles, not reworded versions of the same search.
- Do NOT add words like "latest news" or "expert analysis" unless they genuinely fit.
- Only include a year if the topic type is "current", and then use the current year ({date.today().year}) in at most ONE of the three queries.
- Keep each query short, like something a person would type into a search engine.

Topic: {topic}"""

    plan = planner_llm.invoke(prompt)

    print(f"   Topic type: {plan.topic_type}")
    for i, q in enumerate(plan.queries, 1):
        print(f"   {i}. {q}")

    return {"search_queries": plan.queries}


def search_with_retry(query, attempts=3):
    """Try a Tavily search up to 3 times; if it still fails, skip this query."""
    for attempt in range(1, attempts + 1):
        try:
            return tavily.search(query, max_results=3)
        except Exception as e:
            print(f"   ⚠️ Search failed (attempt {attempt}/{attempts}): {type(e).__name__}")
            if attempt == attempts:
                return {"results": []}   # give up on this query, but keep the run going
            time.sleep(3)


def searcher_node(state: ResearchState) -> dict:
    queries = state["search_queries"]
    print(f"🔎 Searcher: running {len(queries)} searches...")

    # URLs we already have (from earlier loops) — skip them
    seen = set()
    for old in state.get("search_results", []):
        seen.add(old.split("\nURL: ")[1].split("\n")[0])

    results = []
    for q in queries:
        print(f"   → {q}")
        response = search_with_retry(q)

        for r in response["results"]:
            if r["url"] in seen:
                continue                     
            seen.add(r["url"])
            content = r["content"][:1000]
            results.append(f"TITLE: {r['title']}\nURL: {r['url']}\nCONTENT: {content}")

    print(f"   Collected {len(results)} new results.")
    return {"search_results": results}


def writer_node(state: ResearchState) -> dict:
    results = state["search_results"]
    print(f"✍️  Writer: drafting report from {len(results)} sources...")

    numbered = format_sources(results)
    # If the critic complained last round, show the old draft + the complaints
    feedback = ""
    if state.get("critique"):
        feedback = f"""
You are REVISING your previous draft, not starting over.

YOUR PREVIOUS DRAFT:
{state['report_draft']}

A fact-checker rejected these claims from it:
{state['critique']}

When revising:
- Keep everything that was not flagged, unchanged.
- For each flagged claim: if the sources now clearly support it, keep it with the right citation. Otherwise DELETE it.
- Prefer deleting over rewording. A shorter accurate report beats a longer shaky one.
- Do NOT add any new claims that are not directly stated in the sources, including in tables.
"""

    prompt = f"""You are a research analyst. Write a clear, well-structured report on the topic below,
using ONLY the numbered sources provided. Today is {date.today()}.

Rules:
- Start with a short title, then a 2-3 sentence summary.
- Use markdown headings for 3-5 sections.
- After every factual claim, cite the source number(s) like [1] or [2][5].
- Do not invent facts that aren't in the sources. If the sources disagree or are thin, say so.
- Treat vendor/marketing claims as claims, not facts (e.g. "Sumsub says...").
- If the evidence is mostly from vendors or is thin, include a short "Limitations" section saying so.
- End with a "Sources" section listing each number with its title and URL.
- Statements about the quality or gaps of the evidence (e.g. "no firm-level data exists") belong ONLY in the Limitations section, never in the main sections.
- Never apply a general finding to a specific group (e.g. "small businesses", "Africa", "women") unless the source itself mentions that group. If the sources don't cover the group the topic asks about, say so in the Limitations section instead.
{feedback}
Topic: {state['topic']}

Sources:
{numbered}"""

    response = llm.invoke(prompt)
    print("   Draft complete.")
    return {"report_draft": response.content}

# The shape of the critic's verdict
# One checked claim
class ClaimCheck(BaseModel):
    claim: str = Field(description="The factual claim, shortened to max 20 words")
    cited: str = Field(description="Source numbers cited for it, e.g. '[3]' or 'none'")
    verdict: Literal["supported", "unsupported", "overstated", "vendor_as_fact"]
    reason: str = Field(description="One short sentence explaining the verdict")


# The critic's full review
class ClaimReview(BaseModel):
    checks: List[ClaimCheck] = Field(description="Between 10 and 15 of the most important factual claims, each checked")
    follow_up_queries: List[str] = Field(default_factory=list, description="Up to 2 search queries to fix failed claims. Empty if all passed.")


BAD_VERDICTS = {"unsupported", "overstated", "vendor_as_fact"}


def critic_node(state: ResearchState) -> dict:
    iteration = state.get("iteration", 0) + 1
    print(f"🧐 Critic: checking claims (round {iteration})...")

    all_results = state["search_results"]
    report = state["report_draft"]

    # Only look at the main text, not the Sources list at the end
    body = report[: report.rfind("Sources")] if "Sources" in report else report

    # Find every citation number, in [3] or 【3】 style
    cited = sorted({int(n) for n in re.findall(r"[\[【](\d+)[\]】]", body)})
    cited = [n for n in cited if 1 <= n <= len(all_results)]
    if not cited:                      # no citations found → fall back to all sources
        cited = list(range(1, len(all_results) + 1))

    print(f"   Sending the critic {len(cited)} cited sources (of {len(all_results)}).")
    numbered = format_sources(all_results, cited)

    prompt = f"""You are a meticulous fact-checker. Check the report CLAIM BY CLAIM.

Check between 10 and 15 of the most important factual claims in the report
(or every claim, if the report has fewer than 10):
1. Write the claim (max 20 words) and the source numbers it cites.
2. Read ONLY that cited source's text below. It is the only evidence that counts.
3. Give exactly one verdict:
   - "supported": the cited source clearly says this.
   - "unsupported": the cited source does not say this, or no source is cited, or the source name is wrong.
   - "overstated": the source says something weaker or narrower (e.g. "emerging" vs "fastest-growing",
     global figure presented as regional, one opinion presented as "consensus").
   - "vendor_as_fact": a company's claim about its own product stated as neutral fact instead of attributed.
4. Give one short reason.

Do not judge the report's style or overall quality. Only check claims against sources.
Skip the Limitations section and any statements describing the sources themselves (e.g. "these are vendor blogs").
If any claim fails, suggest up to 2 search queries that would find proper evidence.

REPORT:
{state['report_draft']}

SOURCES:
{numbered}"""

    critic_llm = llm.with_structured_output(ClaimReview, method="json_schema").with_retry(stop_after_attempt=2)
    review = critic_llm.invoke(prompt)

    # Python makes the final decision, not the LLM
    failed = [c for c in review.checks if c.verdict in BAD_VERDICTS]
    passed = len(review.checks) - len(failed)
    is_ok = len(failed) == 0

    print(f"   Checked {len(review.checks)} claims: {passed} passed, {len(failed)} failed.")
    for c in failed:
        print(f"   ❌ [{c.verdict}] {c.claim}  →  {c.reason}")

    if len(review.checks) < 8:
        print("   ⚠️ Critic checked very few claims — treat this approval with caution.")
    
    # Turn the failures into clear instructions for the writer
    problems = "\n".join(
        f"- [{c.verdict}] \"{c.claim}\" (cited {c.cited}): {c.reason}" for c in failed
    )

    if is_ok:
        print("   ✅ All claims passed.")

    return {
        "is_satisfactory": is_ok,
        "critique": problems,
        "search_queries": review.follow_up_queries,
        "iteration": iteration,
        "claims_checked": len(review.checks),
        "claims_failed": len(failed),
    }

def cleanup_node(state: ResearchState) -> dict:
    """After the last round: delete the claims the critic still rejected. Nothing else."""
    print("🧹 Clean-up: removing claims the critic still flagged...")

    prompt = f"""Below is a research report and a list of claims a fact-checker rejected.
Delete each rejected claim (or the part of the sentence that makes it).
Fix any sentence that no longer reads well. Change NOTHING else and add NO new content.

REJECTED CLAIMS:
{state['critique']}

REPORT:
{state['report_draft']}"""

    response = llm.invoke(prompt)
    print("   Clean-up complete.")
    return {"report_draft": response.content}