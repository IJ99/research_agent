import os
from typing import List
from datetime import date
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from tavily import TavilyClient

from app.state import ResearchState

load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# The exact shape we want the LLM to return
class SearchPlan(BaseModel):
    queries: List[str] = Field(description="3 focused, distinct web search queries")


def planner_node(state: ResearchState) -> dict:
    topic = state["topic"]
    print(f"🧠 Planner: breaking down '{topic}'...")

    planner_llm = llm.with_structured_output(SearchPlan, method="json_schema")

    prompt = f"""You are a research planner. Today is {date.today()}.
Break this topic into exactly 3 web search queries that together cover it well.
Each query should target a different angle (e.g. facts/background, recent news, expert analysis).
Keep each query short, like something a person would type into a search engine.

Topic: {topic}"""

    plan = planner_llm.invoke(prompt)

    for i, q in enumerate(plan.queries, 1):
        print(f"   {i}. {q}")

    return {"search_queries": plan.queries}


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
        response = tavily.search(q, max_results=3)

        for r in response["results"]:
            if r["url"] in seen:
                continue                      # duplicate, skip it
            seen.add(r["url"])
            content = r["content"][:500]
            results.append(f"TITLE: {r['title']}\nURL: {r['url']}\nCONTENT: {content}")

    print(f"   Collected {len(results)} new results.")
    return {"search_results": results}


def writer_node(state: ResearchState) -> dict:
    results = state["search_results"]
    print(f"✍️  Writer: drafting report from {len(results)} sources...")

    # Number each source so the LLM can cite them as [1], [2], ...
    numbered = "\n\n".join(f"[{i}] {r}" for i, r in enumerate(results, 1))

    prompt = f"""You are a research analyst. Write a clear, well-structured report on the topic below,
using ONLY the numbered sources provided. Today is {date.today()}.

Rules:
- Start with a short title, then a 2-3 sentence summary.
- Use markdown headings for 3-5 sections.
- After every factual claim, cite the source number(s) like [1] or [2][5].
- Do not invent facts that aren't in the sources. If the sources disagree or are thin, say so.
- End with a "Sources" section listing each number with its title and URL.

Topic: {state['topic']}

Sources:
{numbered}"""

    response = llm.invoke(prompt)
    print("   Draft complete.")
    return {"report_draft": response.content}