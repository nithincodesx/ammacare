"""Flow tests for AmmaCare V1 agent brain. Run: python3 tests/test_agent.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import agent  # noqa: E402
import store  # noqa: E402

P = store.DEFAULT_PROFILE


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    assert cond, name


# 1. Medicine refill (Manglish, like Maitri's BP tablet example)
t = agent.prepare_task("Amme, ente BP tablet theerarayi", P)
check("refill intent", t["intent"] == "medicine_refill")
check("refill waits for approval", t["status"] == "pending_approval")
check("refill uses pharmacy memory", "Sevana Medicals" in t["parent_reply"])

# 2. Ride booking with day + time extraction
t = agent.prepare_task("Nale 10 manikku Dr. Sharma de clinicil pokanam, oru auto venam", P)
check("ride intent", t["intent"] == "ride_booking")
check("ride day extracted", t["details"]["when"].startswith("tomorrow"))

# 3. Emergency beats everything else, even if other keywords appear
t = agent.prepare_task("Veetil veezhnu, sahayam venam, tablet edukkan pattilla", P)
check("emergency intent wins", t["intent"] == "emergency")
check("emergency is an alert, not a task", t["status"] == "alert")
check("emergency reply mentions 112", "112" in t["parent_reply"])

# 4. Check-in reply is logged, not sent for approval
t = agent.prepare_task("Ravile tablet kazhichu, sugam aanu", P)
check("checkin intent", t["intent"] == "checkin_reply")
check("checkin logged directly", t["status"] == "logged")

# 5. Malayalam script works too
t = agent.prepare_task("എന്റെ മരുന്ന് തീരാറായി", P)
check("malayalam script refill", t["intent"] == "medicine_refill")

# 6. Reminders come from the profile
r = agent.todays_reminders(P)
check("3 reminder slots from profile", len(r) == 3)

# 7. Weekly summary generates from data
s = agent.weekly_summary({"checkins": [1, 2], "alerts": [], "tasks": []})
check("weekly summary mentions check-ins", "2 daily check-in" in s)

print("\nAll flows passed.")
