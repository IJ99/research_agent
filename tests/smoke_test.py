import os
from dotenv import load_dotenv

load_dotenv()  # reads your .env file into environment variables

# --- Test 1: the LLM (Groq) ---
try:
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="openai/gpt-oss-120b")
    reply = llm.invoke("Say hello in exactly 5 words.")
    print("✅ Groq works:", reply.content)
except Exception as e:
    print("❌ Groq failed:", e)

# --- Test 2: web search (Tavily) ---
try:
    from tavily import TavilyClient
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = tavily.search("latest AI agent frameworks", max_results=2)
    print("✅ Tavily works:")
    for r in results["results"]:
        print("   -", r["title"], "|", r["url"])
except Exception as e:
    print("❌ Tavily failed:", e)