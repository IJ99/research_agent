from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.graph import agent

app = FastAPI(
    title="Autonomous Web Research Agent API",
    description="Give it a topic; it plans, searches, writes and fact-checks a cited report.",
)


# What the caller must send
class ResearchRequest(BaseModel):
    topic: str = Field(min_length=5, examples=["How AI is used to detect fraud in African fintech"])


# What the caller gets back
class ResearchResponse(BaseModel):
    topic: str
    report: str
    approved_by_critic: bool
    rounds_used: int
    sources_used: int


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Research agent is running"}


@app.post("/api/research", response_model=ResearchResponse)
def run_research(request: ResearchRequest):
    initial_state = {
        "topic": request.topic,
        "search_queries": [],
        "search_results": [],
        "report_draft": "",
        "critique": "",
        "iteration": 0,
        "is_satisfactory": False,
    }

    final_state = agent.invoke(initial_state)

    return ResearchResponse(
        topic=request.topic,
        report=final_state["report_draft"],
        approved_by_critic=final_state["is_satisfactory"],
        rounds_used=final_state["iteration"],
        sources_used=len(final_state["search_results"]),
    )