import csv
import os
import time
from datetime import datetime

from app.graph import agent

# The fixed "exam paper": varied topic types
# Lines starting with # are switched off (already done in the first run)
TOPICS = [
    #("baseline", "How AI is used to detect fraud in African fintech"),
    #("timeless", "Explain the second law of thermodynamics"),
    ("nigeria_policy", "Impact of the CBN cashless policy on small businesses in Nigeria"),
    #("recent_health", "Current state of malaria vaccine rollout in Africa"),
    #("conflicting", "Effects of remote work on employee productivity"),
    #("history", "History of the Benin Bronzes repatriation"),
]

RUNS_PER_TOPIC = 1      # increase to 2-3 later for more reliable numbers
PAUSE_SECONDS = 20      # breathing room for Groq's free-tier limits

stamp = datetime.now().strftime("%Y%m%d_%H%M")
os.makedirs("evals/results", exist_ok=True)
os.makedirs(f"evals/reports/{stamp}", exist_ok=True)

rows = []
stop_exam = False       # becomes True if Groq's limit runs out

for category, topic in TOPICS:
    for run in range(1, RUNS_PER_TOPIC + 1):
        print(f"\n===== [{category}] run {run}: {topic} =====")
        start = time.time()
        row = {"category": category, "topic": topic, "run": run}

        try:
            state = agent.invoke({
                "topic": topic,
                "search_queries": [],
                "search_results": [],
                "report_draft": "",
                "critique": "",
                "iteration": 0,
                "is_satisfactory": False,
            })
            row.update({
                "status": "ok",
                "approved": state["is_satisfactory"],
                "rounds": state["iteration"],
                "sources": len(state["search_results"]),
                "claims_checked": state.get("claims_checked", 0),
                "claims_failed": state.get("claims_failed", 0),
                "report_words": len(state["report_draft"].split()),
            })
            # Save the report so you can read it later
            with open(f"evals/reports/{stamp}/{category}_run{run}.md", "w", encoding="utf-8") as f:
                f.write(state["report_draft"])

        except Exception as e:
            # One failure shouldn't kill the whole exam...
            row.update({"status": f"error: {type(e).__name__}"})
            print(f"   ⚠️ Failed: {type(e).__name__}")
            print(f"   Details: {str(e)[:400]}")
            # ...but if Groq's limit has run out, everything after will fail too
            if type(e).__name__ == "RateLimitError":
                print("\n⛔ Groq rate limit reached — stopping the exam early.")
                stop_exam = True

        row["seconds"] = round(time.time() - start, 1)
        rows.append(row)

        if stop_exam:
            break                       # leave the "runs" loop
        time.sleep(PAUSE_SECONDS)

    if stop_exam:
        break                           # leave the "topics" loop

# Save all scores to a CSV (opens in Excel)
fields = ["category", "topic", "run", "status", "approved", "rounds", "sources",
          "claims_checked", "claims_failed", "report_words", "seconds"]
csv_path = f"evals/results/eval_{stamp}.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

# Quick summary
ok = [r for r in rows if r["status"] == "ok"]
print("\n========== SUMMARY ==========")
print(f"Completed:      {len(ok)}/{len(rows)}")
if ok:
    print(f"Approved:       {sum(r['approved'] for r in ok)}/{len(ok)}")
    print(f"Avg rounds:     {sum(r['rounds'] for r in ok) / len(ok):.1f}")
    print(f"Avg seconds:    {sum(r['seconds'] for r in ok) / len(ok):.0f}")
    print(f"Final failed claims (total): {sum(r['claims_failed'] for r in ok)}")
print(f"\nScores saved to {csv_path}")