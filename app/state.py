from typing import TypedDict, List, Annotated
import operator


class ResearchState(TypedDict):
    topic: str                                          # what the user wants researched
    search_queries: List[str]                           # written by planner
    search_results: Annotated[List[str], operator.add]  # written by searcher (adds up)
    report_draft: str                                   # written by writer
    critique: str                                       # written by critic (later)
    iteration: int                                      # how many loops so far
    is_satisfactory: bool                               # critic's verdict