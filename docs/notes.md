# Research Agent: Build Notes

Personal log of what I built, why, and what I learned. Target: finished by end of 2026.

Repo: https://github.com/IJ99/research_agent

---

## Progress (as of Oct 22, 2026)

| Phase | Status |
|---|---|
| 1. Setup (venv, keys, smoke test) | ✅ Done (Oct 19) |
| 2. Core agent: planner → searcher → writer | ✅ Done (Oct 20) |
| 3. Critic + self-correction loop | ✅ Done (Oct 20) |
| 4. FastAPI endpoint + error handling | ✅ Done (Oct 21) |
| Pushed to GitHub | ✅ Done (Oct 21) |
| Claim-by-claim critic | ✅ Done, merged (Oct 22) |
| Evaluation suite | 🟡 Built; baseline 2 of 6 topics done (Groq daily limit) |
| Smarter planner, longer sources, final clean-up pass | ⏳ Next, after baseline |
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
| Planner | `topic` | `search_queries` | Structured output (`json_schema`) → exactly 3 queries. Given today's date. |
| Searcher | `search_queries` | `search_results` | 3 Tavily results per query, trimmed to 500 chars, skips URLs seen in any round. |
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

---

## To-do / improvement ideas

**Next**
- [ ] Finish the baseline: run the remaining 4 exam topics in two batches (daily token limit)
- [ ] **Smarter planner:** choose search angles to fit the topic type (timeless / policy / recent / contested); no forced "latest news"
- [ ] **Longer source text** (500 → ~1,500 characters) so the critic stops failing true claims
- [ ] Re-run the exam and compare scores against the baseline

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
