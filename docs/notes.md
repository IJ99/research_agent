# Research Agent: Build Notes

Personal log of what I built, why, and what I learned. Target: finished by end of 2026.

Repo: https://github.com/IJ99/research_agent

---

## Progress (as of Oct 23, 2026)

| Phase | Status |
|---|---|
| 1. Setup (venv, keys, smoke test) | ✅ Done (Oct 19) |
| 2. Core agent: planner → searcher → writer | ✅ Done (Oct 20) |
| 3. Critic + self-correction loop | ✅ Done (Oct 20) |
| 4. FastAPI endpoint + error handling | ✅ Done (Oct 21) |
| Pushed to GitHub (+ short README) | ✅ Done (Oct 21–22) |
| Claim-by-claim critic | ✅ Done, merged (Oct 22) |
| Evaluation suite + baseline | ✅ Done (Oct 22–23): **5/6 approved, avg 2.0 rounds** |
| Smarter planner + longer sources (1,000 chars) | 🟡 On branch `planner-sources`; one test passed; full exam re-run next |
| Final clean-up pass | ⏳ Later |
| 5. Ollama (local GPU) | ⏳ Later |
| README + architecture diagram | ⏳ Last |

---

## Stack

- **LangGraph**: runs the agent as a graph of steps
- **Groq** (`openai/gpt-oss-120b`): free LLM API. Switched from OpenAI to avoid paid billing
- **Tavily**: web search built for AI agents (free tier)
- **FastAPI + Uvicorn**: web API around the agent
- **python-dotenv**: loads API keys from `.env`
- **Git + GitHub**: version control. `.env` and `venv/` excluded via `.gitignore`

---

## Project structure

```
research-agent/
├── app/
│   ├── state.py      # ResearchState: the shared "whiteboard"
│   ├── nodes.py      # planner, searcher, writer, critic
│   ├── graph.py      # wiring + the critic loop
│   └── main.py       # FastAPI app (/ and /api/research)
├── evals/
│   ├── run_eval.py   # the "exam": fixed topics → scores CSV
│   ├── results/      # one CSV per exam run
│   └── reports/      # saved reports per exam run
├── playground/       # experiments and manual test scripts
├── tests/
│   └── smoke_test.py # checks Groq + Tavily keys work
├── docs/
│   └── notes.md      # this file
├── .env              # API keys (never committed)
├── .gitignore
└── requirements.txt
```

**Commands**
- Run the agent once: `python -m playground.run_agent` (saves `report.md`)
- Start the API: `uvicorn app.main:app --reload`, then open http://127.0.0.1:8000/docs
- Run the exam: `python -m evals.run_eval`
- Save work: `git add .` → `git commit -m "..."` → `git push`

---

## How LangGraph works (in one picture)

- **State** = a shared whiteboard with labelled boxes. Only declared fields are kept.
- **Nodes** = workers. Each reads the board, does one job, and returns *only* the fields it changed.
- **Edges** = the rota. They decide who goes next.
- **Conditional edges** = the manager making a decision (e.g. loop back or stop).
- **`graph.py`** is the manager. `nodes.py` says *what* each step does; `graph.py` says *in what order*, and *when to loop*.

---

## The agent

```
START → planner → searcher → writer → critic ──(all claims pass, or 3 rounds)──→ END
                     ▲                   │
                     └───(claims failed)─┘
```

| Node | Reads | Writes | Notes |
|---|---|---|---|
| Planner | `topic` | `search_queries` | First classifies the topic (timeless / history / current / policy / contested), then writes 3 queries with angles that fit that type. Only "current" topics get a year, and only the current year. *(On branch `planner-sources`.)* |
| Searcher | `search_queries` | `search_results` | 3 Tavily results per query, trimmed to 1,000 chars (was 500), skips URLs seen in any round. |
| Writer | `search_results`, `critique`, previous `report_draft` | `report_draft` | Cites numbered sources [1]. Uses ONLY sources. Attributes vendor claims. Adds Limitations. When revising, it sees its previous draft, keeps unflagged text, and prefers deleting flagged claims over rewording. |
| Critic | `report_draft`, `search_results` | `is_satisfactory`, `critique`, `search_queries`, `iteration`, `claims_checked`, `claims_failed` | Checks up to 15 claims one by one: supported / unsupported / overstated / vendor_as_fact. **Python decides**: approved only if zero claims fail. Skips the Limitations section. |

Key state trick: `search_results` uses `Annotated[List[str], operator.add]`, so each round **adds** results instead of replacing them.

---

## The API (Phase 4)

- `GET /` → health check
- `POST /api/research` with `{"topic": "..."}` → `report`, `approved_by_critic`, `rounds_used`, `sources_used`, `duration_seconds`
- `topic` must be at least 5 characters (otherwise FastAPI returns `422`)
- Endpoint uses `def`, not `async def`, because the agent is synchronous. With `async def` the whole server would freeze during a report.
- Error handling: Groq rate limit → `429`, provider error → `502`, anything unexpected → `500`. Callers get a short safe message; the full traceback goes to the server log only.
- Tested by breaking the model name on purpose → clean `502`.

---

## Problems I hit and how I fixed them

| Problem | Cause | Fix |
|---|---|---|
| Slow/locking installs | Project was inside OneDrive | Moved to `C:\Users\johnc\projects` |
| `activate` blocked | Windows script policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Keys not found | Files named `env` / `gitignore` (no dot) | Renamed to `.env` / `.gitignore` |
| `model_not_found` (404) | Groq retired `llama-3.3-70b-versatile` | Listed available models via API, chose `gpt-oss-120b` |
| `tool_use_failed` (400) | Model ignored the tool-calling format | `with_structured_output(..., method="json_schema")` |
| New state field silently vanished | Field not declared in the State class | Always add new fields to the State first |
| Duplicate sources in report | Two queries found the same page | Searcher tracks seen URLs in a `set` |
| `429` with Qwen as critic | Free tier: 1,000 output tokens/min for that model | `max_tokens=900` (later reverted model anyway) |
| `No module named ...` | Folder created inside `app/` instead of the project root | Moved folders to the top level; click the root folder before creating new ones |
| `403 Access denied` from Groq | Network/VPN change | Switched network |
| Critic crashed: `follow_up_queries` missing | Model left out a field | `Field(default_factory=list)` + `.with_retry(stop_after_attempt=2)` |
| GitHub "Repository not found" | Repo was named `research_agent` (underscore) | `git remote set-url origin` with the exact URL |
| Exam failed with `RateLimitError` | Hit Groq limits (see below) | `max_retries=6`; exam stops early and prints error details |

**Habit:** read tracebacks from the bottom up. The last line is the real error.

---

## Groq free-tier limits (gpt-oss-120b)

- **~8,000 tokens per minute.** One writer or critic request ≈ 7,000 tokens, so it nearly fills the minute on its own.
- **200,000 tokens per day** (rolling 24 hours, not a midnight reset).
- **One research report ≈ 40,000–60,000 tokens**, so only about **3–4 reports per day**.
- Each model has its own separate quota.
- The Usage page shows a "cost", but that's only what it would cost on a paid plan. No charge without a card on file.

---

## Experiments and findings

1. **No critic vs critic.** The first report looked polished but stated vendor marketing as fact ("90% fewer errors"), used a weak source for a big stat, and had a duplicate source. With the critic, reports attribute vendor claims and include an honest Limitations section.

2. **Critic too strict.** It kept rejecting because "independent academic studies" barely exist, which is unfixable by searching. Fix: split problems into **fixable** (unsupported or overstated claims → reject) vs **unfixable** (thin evidence → approve if the report states the limitation).

3. **Same model vs different model as critic.** Tried Qwen as an independent critic. It approved the same errors (wrong source name "GFMA", one vendor blog presented as "consensus"). **Conclusion: the problem is holistic judging, not the model.**

4. **Runs are not repeatable.** Same code and topic: one run approved in round 1, another rejected all 3 rounds. Search results and wording change each run. **To judge the agent, I need several runs on several topics, not one.**

5. **Claim-by-claim critic.** The LLM checks each claim individually; plain Python makes the final decision. It catches precise errors the holistic critic missed: "Visa **and Mastercard**" when the source only mentions Visa, a global statistic presented as African, "emerging" turned into "fastest-growing", one opinion presented as "consensus".

6. **Whack-a-mole.** The writer couldn't see its previous draft, so every round it rewrote from scratch and added new unsupported sentences. Failures went 2 → 4 → 2 and it was never approved. **Fix:** pass the previous draft to the writer and tell it to revise, keep unflagged text, and prefer deleting. **After:** 1 → 0 and 1 → 1 → 0, both approved.

7. **First exam (partial baseline, Oct 22).**
   - Fraud: approved in 2 rounds. Thermodynamics: not approved after 3 rounds. CBN: crashed (rate limit).
   - **The planner forces a "news" angle on timeless topics.** "2024-2026 research on entropy" pulled in a speculative "gravity from entropy" article, and the agent wasted two rounds chasing it.
   - **The 500-character cut hurts the critic.** It failed the true Kelvin-Planck statement because the useful part of the Britannica page had been cut off. Other failures: "source provides only publication details."
   - **First drafts are padded with general knowledge** (7 failed claims in the fraud draft, e.g. "sub-second response times"). The revise loop cleans them up.

8. **Complete baseline (Oct 22–23).**

   | Topic | Type | Rounds | Result |
   |---|---|---|---|
   | AI fraud in African fintech | baseline | 2 | ✅ |
   | Second law of thermodynamics | timeless | 3 | ❌ (2 claims still failing) |
   | CBN cashless policy | Nigeria policy | 1 | ✅ |
   | Malaria vaccine rollout | recent health | 2 | ✅ |
   | Remote work productivity | conflicting | 2 | ✅ |
   | Benin Bronzes repatriation | history | 2 | ✅ |

   **Score: 5/6 approved, avg 2.0 rounds.** This is the number every change has to beat.
   - Good critic catches: "hybrid work has the highest satisfaction" (source only gave the 51% share); "next-gen malaria vaccines promise higher efficacy" (not in source).
   - **Planner problem confirmed on every topic:** "latest news Benin Bronzes return 2024", "2025 remote work productivity news". Forced news angles and random years.
   - **Short sources cause false failures again:** the 1897 punitive expedition (a well-known fact) failed because the 500-char snippets didn't include it, and a whole round was spent proving it.
   - **15-claim cap:** "15 checked, 15 passed" may hide unchecked claims if the report has more than 15. Need to check report length.
   - Ran 4 topics in one sitting once the rolling daily quota had freed up (~23 min).

9. **Smarter planner + longer sources (Oct 23, branch `planner-sources`).**
   - Planner now classifies the topic type before writing queries, with no forced "latest news" or random years.
   - Sources raised from 500 to **1,000** characters, not 1,500: at 500 chars a writer/critic request is already ~4–5K input tokens, and tripling the text could push a single round-3 request over the 8K tokens/minute limit on its own (it would then never succeed).
   - **First test, thermodynamics:** classified as `timeless`; queries "definition / how entropy increases / everyday examples" (no news, no year). **Before: ❌ not approved after 3 rounds. After: ✅ approved in round 1.**
   - One run only. Needs the full exam before merging.

---

## To-do / improvement ideas

**Next**
- [x] Finish the baseline (5/6 approved, avg 2.0 rounds)
- [x] **Smarter planner:** classify topic type, angles to fit; no forced "latest news" or years *(on branch)*
- [x] **Longer source text:** 500 → 1,000 characters *(on branch)*
- [ ] Re-run the full exam on `planner-sources` (all 6 topics, ~2 days of quota) and compare with the baseline
- [ ] If better: merge `planner-sources` into `main`
- [ ] Check the 15-claim cap: do reports have more than 15 claims? If so, raise the cap or keep reports shorter
- [ ] Add `topic_type` to the exam CSV, to check the planner's classifications

**Quality**
- [ ] **Final clean-up pass:** when stopping at max rounds, have the writer delete the claims the critic last flagged
- [ ] Writer should list only sources it actually cited (no junk in the Sources list)
- [ ] Stop invented text in tables (e.g. "How it works" columns)
- [ ] Filter or down-rank social media sources (a Facebook group post was used as a source)
- [ ] Critic shouldn't suggest searches whose only purpose is to justify writer filler

**Cost and speed**
- [ ] Reduce tokens per report (e.g. `gpt-oss-20b` for the planner, fewer or shorter sources per critic round)
- [ ] Background jobs for long API requests (a report can take 3+ minutes)

**Bigger refactor**
- [ ] Structured sources: ID, title, URL, domain, content, date (instead of one text string)

**Later**
- [ ] Phase 5: Ollama on the RTX 4050 (6GB VRAM), compared against Groq using the exam
- [ ] README with a Mermaid architecture diagram, quickstart, and the findings above

---

## Next project: Nigerian fact-checker

### Vision

> **Before you forward it, check it.** Send any suspicious message (text, picture or voice note, in English, Pidgin, Yoruba, Hausa or Igbo) and get a clear, sourced verdict back in your own language.

### The problem

"Please beware!!!" broadcast messages spread fast in Nigerian WhatsApp groups: fake government giveaways, health scares ("NAFDAC says this drink is poisoned"), scam warnings, "forward to 10 people". People forward them to protect their family, but many are false, outdated or scams. **It's for everyone in Nigeria**, not one age group. My mum is a good example of how common it is.

### How it works

```
INPUT LAYER: "understand anything"
  text / picture / voice note, in English / Pidgin / Yoruba / Hausa / Igbo
        │
        ▼
  1. Picture → read the text in it + describe the image
  2. Voice note → speech-to-text (Whisper, available on Groq)
  3. Detect the language → translate the claim into English
        │
        ▼
CHECKING CORE: adapted research agent, in English
  claim extractor → planner → searcher → judge → critic
        │
        ▼
OUTPUT LAYER: "reply the way they asked"
  translate the verdict back into the user's language
```

- **Why check in English in the middle:** most trusted sources (CBN, NAFDAC, major Nigerian outlets, fact-checkers) publish in English. One checking core serves every language.
- **Changes from the research agent:**
  - **Claim extractor (new):** pulls the one checkable claim out of a messy message
  - **Planner:** plans searches to confirm *or* disprove the claim
  - **Searcher:** prefers trusted sources (government, CBN, NAFDAC, major outlets, fact-checkers) and drops social media posts
  - **Judge (replaces writer):** a verdict plus 1–2 sentences
  - **Critic:** the claim-by-claim critic; weak evidence pushes the verdict toward "Not confirmed"

### Verdicts

- **True**: reliable sources confirm it
- **False**: reliable sources contradict it
- **Misleading**: partly true, but exaggerated or missing context (e.g. a real photo from a different place or year)
- **Not confirmed**: no reliable source confirms or denies it yet. Always better than guessing.

### Reply design (works for everyone)

- **Verdict first**, then 1–2 plain sentences, then sources. Readable in five seconds.
- **Respectful tone**: "NAFDAC has not issued this warning", never "you fell for fake news".
- **Forwardable**: short enough to send straight back to the group, so the correction spreads like the rumour did.
- **Safety advice for scams**: "Don't click the link. Don't share your BVN."
- Note that it's an AI tool and can make mistakes.

### Pictures: what's realistic

- ✅ **Read the writing** in screenshots, flyers and "warning" posters, then check it like a text claim
- ✅ **Describe the image** and check what it claims to show
- 🟡 **Find where a photo first appeared** (reverse image search): "real photo, but from Ghana in 2023, not Lagos today"
- ❌ **Don't promise** to detect edited photos or deepfakes. Even experts struggle. Check the *claim*, not the pixels.

### Build order (one at a time, each tested before the next)

| Step | Feature | Difficulty | Notes |
|---|---|---|---|
| 1 | English text | ✅ Easiest | The core. Get it accurate and measured first. |
| 2 | Pictures (screenshots, flyers) | 🟢 Moderate | Reading text works well; edited-photo detection does not |
| 3 | Pidgin (text) | 🟢 Moderate | Models handle Pidgin reasonably well; test it |
| 4 | Voice notes (English / Pidgin) | 🟡 Moderate | Whisper on Groq; accents and Pidgin may reduce accuracy |
| 5 | Yoruba, Hausa, Igbo (text) | 🟠 Harder | Models are weaker; tone marks matter; test with native speakers, one language at a time |
| 6 | Voice notes in Yoruba / Hausa / Igbo | 🔴 Hard | General speech-to-text is weak here; may need African-language speech models |
| 7 | WhatsApp connection | 🟡 Moderate | WhatsApp Business API (or a service like Twilio). Test as a web page / API first. |
| 8 | Video | 🔴 Hard | Audio → transcribe, a few frames → describe. Build last. |

**Rule:** don't build everything at once. Many half-working features are worse than one reliable one. A wrong verdict in Hausa is still wrong, and harder for me to spot.

### How I'll know it works (evaluation)

- **Answer key from professional fact-checkers:** collect 30–50 Nigerian claims already checked by Dubawa / Africa Check, with their verdicts. Run my agent several times on each and measure how often it agrees.
- ⚠️ **Avoid the "found the marking scheme" trap:** the searcher may find the fact-checker's own article and copy its verdict. Run the test **twice**: with fact-checker sites allowed (realistic use) and with them excluded (tests real reasoning). Report both numbers.
- **Start with health, finance and scam claims** (NAFDAC, CBN, fake grants), where facts are clearer, before election claims.
- **Real messages:** collect forwarded "beware" texts, pictures and voice notes from family and friends. Remove names and phone numbers, and **keep them out of the public repo** (private data).
- **Languages:** native speakers check whether the agent understood the claim and whether the reply makes sense. Their judgement is the answer key.
- **Track cost:** Groq's free tier is ~200K tokens/day, so design each check to be much cheaper than a research report.

### Rules

- Stay politically neutral; judge only by evidence.
- Always show sources.
- Say "Not confirmed" when unsure.
- Never store or publish people's private messages, names or numbers.

### What makes it different

| | Google | General chatbots (ChatGPT, Meta AI) | Existing fact-check bots | This project |
|---|---|---|---|---|
| Clear verdict, not just links | ❌ | ⚠️ | ✅ | ✅ |
| Checks brand-new rumours live | ⚠️ (you do the work) | ⚠️ | ❌ (mostly existing fact-checks) | ✅ |
| Prefers trusted Nigerian sources | ❌ | ❌ | ✅ | ✅ |
| Self-checks each claim before replying | ❌ | ❌ | n/a | ✅ |
| Says "Not confirmed" instead of guessing | n/a | ⚠️ | ✅ | ✅ |
| Pidgin, Nigerian languages, voice notes | ❌ | ⚠️ | ⚠️ | ✅ (goal) |
| Measured accuracy against professionals | n/a | ❌ | n/a | ✅ |

Realistic positioning: not "a bot for millions of users" (hard to compete with Meta AI on reach), but **a Nigeria-specialised fact-checker with proven accuracy**. It could also help human fact-checkers by drafting research on new claims quickly.

### What I learned from Dubawa (Oct 23)

Dubawa is a West African fact-checking project run by the Nigerian non-profit **CJID**. It's non-partisan, follows the **IFCN** fact-checking principles, and runs a WhatsApp tipline. Its process is a ready-made blueprint for my agent.

**Their process → my agent**

| Dubawa | My agent |
|---|---|
| Only checks claims that **can be checked**; skips opinions and predictions | **Claim extractor** pulls out the checkable claim, or says "this is an opinion" |
| Researches with five source rules (below) | **Searcher + critic** apply the same rules |
| Editors "fact-check the fact-check", then a copy editor reviews | **Critic** checks the judge's verdict |
| Every story approved by an editor before publishing | For sensitive topics (elections), consider a **human approval** step |
| Contacts the person who made the claim | ❌ My agent can't. Note it in Limitations. |

**Their five source rules (use these in the searcher and critic)**

| Prefer | Over |
|---|---|
| Named sources | Unnamed |
| Authoritative (official, expert) | Random |
| Independent | Self-interested |
| Verifiable evidence | Mere assertions |
| Multiple sources | A single source |

**Their ratings and my mapping (needed for a fair comparison)**

| Dubawa rating | Meaning | Counts as (my verdict) |
|---|---|---|
| TRUE | Everything correct | True |
| MOSTLY TRUE | Most parts correct (often 3+ claims) | True |
| FALSE | Wrong, including fabricated / impersonation content | False |
| MOSTLY FALSE | Most parts wrong | False |
| MISLEADING (wrong / missing context) | True-sounding but out of context | Misleading |
| MISLEADING (insufficient evidence) | Can't be verified | Not confirmed |

- Record Dubawa's **exact** rating for each test claim, and read the article to tell the two kinds of Misleading apart.
- Facebook-sourced claims sometimes use Facebook's labels instead (False, Partly False, Missing Context, True, Satire). Record which system was used.
- WhatsApp messages often contain several claims: check each separately, then give an overall verdict (like Mostly True / Mostly False).

**Choosing test claims:** use their **Fact Checks** only (not Explainers or Media Literacy). Start with the **Health, Economy and Spoofs** themes; leave Politics and Elections for later.

**Reply idea from their media-literacy work:** sometimes add a one-line tip, e.g. "Government agencies never ask for your BVN on WhatsApp."

**Positioning:** a potential **partner**, not a competitor. CJID's goals include building tech tools against misinformation, and its DAIDAC programme (AI in Journalism; Digital Fraud and Cybercrime) wants technologists to build AI tools with journalists. Its digital-fraud focus overlaps with my fintech fraud background. **Contact them only after V1 works**, with a demo and an accuracy number.

### Timeline

| When | What |
|---|---|
| Late Oct | Finish the research agent: ~~baseline exam~~ ✅, ~~planner + source fixes~~ ✅ (on branch), re-run the exam and record before/after |
| Nov | Fact-checker V1 on a new branch (`fact-checker`): English text in, verdict out. Build the answer-key test set and exam. |
| Early Dec | V2: trusted-source filter, re-test, compare accuracy. Start pictures. |
| Mid–late Dec | API + simple web page, README, demo |
| 2027 | Pidgin, voice notes, Yoruba / Hausa / Igbo, WhatsApp, video |
