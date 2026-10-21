import logging
import time

import groq
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.graph import agent

# Logger: full error details go to YOUR terminal, not to the caller
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research-agent")

app = FastAPI(
    title="Autonomous Web Research Agent API",
    description="Give it a topic; it plans, searches, writes and fact-checks a cited report.",
)


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=5, examples=["How AI is used to detect fraud in African fintech"])


class ResearchResponse(BaseModel):
    topic: str
    report: str
    approved_by_critic: bool
    rounds_used: int
    sources_used: int
    duration_seconds: float


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

    start = time.time()
    try:
        final_state = agent.invoke(initial_state)

    # Order matters: most specific errors first
    except groq.RateLimitError:
        logger.warning("Groq rate limit hit for topic: %s", request.topic)
        raise HTTPException(
            status_code=429,
            detail="The AI model's free-tier rate limit was reached. Please wait a minute and try again.",
        )
    except groq.AuthenticationError:
        logger.error("Groq API key is invalid or missing")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error. Please contact the administrator.",
        )
    except groq.APIError:
        logger.exception("Groq API error")
        raise HTTPException(
            status_code=502,
            detail="The AI model provider returned an error. Please try again later.",
        )
    except Exception:
        logger.exception("Unexpected error while researching: %s", request.topic)
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while researching. Please try again.",
        )

    duration = round(time.time() - start, 1)
    logger.info("Finished '%s' in %ss (%s rounds)", request.topic, duration, final_state["iteration"])

    return ResearchResponse(
        topic=request.topic,
        report=final_state["report_draft"],
        approved_by_critic=final_state["is_satisfactory"],
        rounds_used=final_state["iteration"],
        sources_used=len(final_state["search_results"]),
        duration_seconds=duration,
    )