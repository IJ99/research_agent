# Research Agent: Build Notes

Personal log of what I built, why, and what I learned. Target: finished by end of 2026.

---

## Progress so far (Oct 19–20, 2026)

| Phase | Status |
|---|---|
| 1. Setup (venv, keys, smoke test) | ✅ Done |
| 2. Core agent: planner → searcher → writer | ✅ Done |
| 3. Critic + self-correction loop | ✅ Done (critic quality can still improve) |
| 4. FastAPI wrapper | ⏳ Next |
| 5. Local models (Ollama) + README + GitHub | ⏳ Later |

---

## Stack

- **LangGraph**: runs the agent as a graph of steps
- **Groq** (`openai/gpt-oss-120b`): free LLM API. Switched from OpenAI to avoid paid billing
- **Tavily**: web search built for AI agents (free tier)
- **python-dotenv**: loads API keys from `.env`
- **Git**: version control. `.env` and `venv/` are excluded via `.gitignore`

---

## Project structure

```
research-agent/
├── app/
│   ├── state.py      # ResearchState: the shared "whiteboard"
│   ├── nodes.py      # planner, searcher, writer, critic
│   └── graph.py      # wiring + the critic loop
├── playground/       # experiments and manual test scripts
├── tests/
│   └── smoke_test.py # checks Groq + Tavily keys work
├── docs/
│   └── notes.md      # this file
├── .env              # API keys (never committed)
├── .gitignore
└── requirements.txt
```

Run the agent: `python -m playground.run_agent` (output saved to `report.md`)

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
START → planner → searcher → writer → critic ──(approved, or 3 rounds)──→ END
                     ▲                   │
                     └───(not good yet)──┘
```

| Node | Reads | Writes | Notes |
|---|---|---|---|
| Planner | `topic` | `search_queries` | Structured output → exactly 3 queries. Given today's date. |
| Searcher | `search_queries` | `search_results` | 3 Tavily results per query, trimmed to 500 chars, skips duplicate URLs. |
| Writer | `search_results`, `critique` | `report_draft` | Numbered sources → citations like [1]. Uses ONLY sources. Must attribute vendor claims and add a Limitations section. |
| Critic | `report_draft`, `search_results` | `is_satisfactory`, `critique`, `search_queries`, `iteration` | Checks claims against sources. Its follow-up queries overwrite the searcher's to-do list. |

Key state trick: `search_results` uses `Annotated[List[str], operator.add]`, so each round **adds** results instead of replacing them.

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
| `429 rate_limit` with Qwen | Free tier: 1,000 output tokens/min | `max_tokens=900` (later reverted model anyway) |

**Habit:** read tracebacks from the bottom up. The last line is the real error.

---

## Experiments and findings

1. **No critic vs critic.** The first report looked polished but stated vendor marketing as fact ("90% fewer errors"), used a weak source for a big stat, and had a duplicate source. With the critic, reports attribute vendor claims and include an honest Limitations section.

2. **Critic too strict.** It kept rejecting because "independent academic studies" barely exist, which is unfixable by searching. Fix: split problems into **fixable** (unsupported or overstated claims → reject) vs **unfixable** (thin evidence → approve if the report states the limitation).

3. **Same model vs different model as critic.** Tried Qwen (`qwen/qwen3.8-27b`) as an independent critic. It approved the same errors (wrong source name "GFMA", one vendor blog presented as "consensus"). **Conclusion: the problem is holistic judging, not the model.** A critic that reads the whole report at once is lenient with fluent text. Reverted to `gpt-oss-120b`.

4. **Runs are not repeatable.** Same code and topic: one run approved in round 1, another rejected all 3 rounds (but problems shrank 4 → 2 → 1). Search results and wording change each run. **To judge the agent, I need several runs, not one.**

---

## To-do / improvement ideas

- [ ] **Phase 4:** wrap the agent in a FastAPI endpoint (`/api/research`)
- [ ] **Claim-by-claim critic:** list each factual sentence → check its cited source → supported or not (fixes lenient holistic judging)
- [ ] **Final clean-up pass:** when stopping at max rounds, have the writer delete the claims the critic last flagged
- [ ] **Better planner queries:** current ones overlap too much
- [ ] Test on harder topics (e.g. CBN cashless policy impact on small businesses)
- [ ] Phase 5: run nodes on a local model with Ollama (RTX 4050, 6GB VRAM)
- [ ] README with a Mermaid architecture diagram + quickstart
- [ ] Push to GitHub
A Facebook group post is source [4]. The searcher accepts any page Tavily returns. Filtering out social media, or ranking sources by trust, is a good future improvement.
The planner forces a “recent news” angle on everything. Look at your thermodynamics run: “2024-2026 thermodynamics second law research updates.” The laws of thermodynamics don’t have news! The planner prompt says “facts, recent news, expert analysis,” and that template doesn’t fit timeless topics. A smarter planner would choose the angles to fit the topic.
