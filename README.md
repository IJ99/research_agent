# Autonomous Web Research Agent

An AI agent that researches a topic on the web, writes a cited report, and **fact-checks its own claims** before finishing.

> 🚧 **Work in progress.** Full documentation coming by end of 2026. For build notes, experiments and findings, see [`docs/notes.md`](docs/notes.md).

## How it works

```
topic → planner → searcher → writer → critic → report
                     ▲                   │
                     └── claims failed ──┘   (max 3 rounds)
```

1. **Planner**: breaks the topic into search queries
2. **Searcher**: finds sources on the web (Tavily)
3. **Writer**: drafts a report that cites only those sources
4. **Critic**: checks each claim against its cited source. If any claim is unsupported or overstated, the agent searches again and revises.

## Built with

Python · LangGraph · Groq (`gpt-oss-120b`) · Tavily · FastAPI

## Quickstart

```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

Create a `.env` file with your own keys:

```
GROQ_API_KEY=your-groq-key
TAVILY_API_KEY=your-tavily-key
```

Then run the API:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs and try `POST /api/research`.

## Author

Joel Ichibor
