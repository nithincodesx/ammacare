"""Agent brain for AmmaCare V1.

Offline, rule-based intent classification for Malayalam / Manglish / English.
No external APIs and no API key required. If GROQ_API_KEY or GEMINI_API_KEY is
set in the environment later, `llm_refine()` is the single hook to plug an LLM in.
"""
import os
import re

# ---------------------------------------------------------------- intents
INTENT_KEYWORDS = {
    "emergency": [
        "veezhnu", "veenu", "വീണു", "വീണ്", "sahayam", "സഹായം", "help",
        "chest pain", "nenju vedana", "നെഞ്ചുവേദന", "നെഞ്ച് വേദന",
        "ambulance", "ആംബുലൻസ്", "breath", "ശ്വാസം", "blood", "രക്തം",
        "mayakkam", "മയക്കം", "emergency", "അടിയന്തരം",
    ],
    "medicine_refill": [
        "tablet", "ഗുളിക", "medicine", "മരുന്ന്", "marunnu", "refill",
        "theerarayi", "തീരാറായി", "theernnu", "തീർന്നു", "pharmacy",
        "ഫാർമസി", "prescription", "കുറിപ്പ്",
    ],
    "ride_booking": [
        "clinic", "hospital", "ആശുപത്രി", "doctor", "ഡോക്ടർ", "ഡോക്ടറെ",
        "auto", "taxi", "cab", "ride", "pokanam", "പോകണം", "pokan",
    ],
    "reminder_request": [
        "remind", "ormippik", "ഓർമ്മിപ്പിക്ക", "ഓർമിപ്പിക്ക",
        "appointment", "അപ്പോയിന്റ്മെന്റ്",
    ],
    "grocery_order": [
        "grocery", "vegetable", "പച്ചക്കറി", "milk", "പാൽ", "rice",
        "അരി", "order", "ഓർഡർ", "venam", "വേണം",
    ],
    "checkin_reply": [
        "kazhichu", "കഴിച്ചു", "kazhichittundu", "sugam", "സുഖം",
        "fine", "okay", "ok", "nannayi", "നന്നായി", "urangee", "ഉറങ്ങി",
    ],
}

EMERGENCY_REPLY_ML = (
    "അമ്മേ, ഞാൻ ഇപ്പോൾ തന്നെ നിങ്ങളുടെ മകനെ/മകളെ അറിയിക്കുന്നു. "
    "അടിയന്തരമാണെങ്കിൽ 112-ൽ വിളിക്കുക. അടുത്തുള്ള ആരെയെങ്കിലും വിളിക്കാൻ ശ്രമിക്കുക. "
    "(This is not an emergency service — please call 112 if urgent.)"
)


def classify(text: str) -> str:
    """Return the best-matching intent. Emergency always wins."""
    t = " " + text.lower().strip() + " "
    scores = {}
    for intent, words in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for w in words if w in t)
    if scores.get("emergency", 0) > 0:
        return "emergency"
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def _find_time(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s*(manikku|am|pm|o'clock|മണി)", text.lower())
    return m.group(0) if m else None


def _find_day(text: str) -> str:
    t = text.lower()
    if "nale" in t or "നാളെ" in t or "tomorrow" in t:
        return "tomorrow"
    if "innu" in t or "ഇന്ന്" in t or "today" in t:
        return "today"
    return "today"


def prepare_task(text: str, profile: dict) -> dict:
    """Turn a parent message into a caregiver-approvable task (Maitri-style).

    The agent PREPARES, it never executes a purchase/booking by itself.
    """
    intent = classify(text)
    parent = profile.get("parent_name", "Amma")
    task = {"intent": intent, "raw": text, "status": "pending_approval",
            "title": "", "details": {}, "parent_reply": ""}

    if intent == "emergency":
        task["status"] = "alert"  # not a task — an alert, handled by caller
        task["title"] = f"EMERGENCY alert from {parent}"
        task["parent_reply"] = EMERGENCY_REPLY_ML

    elif intent == "medicine_refill":
        last = profile.get("memory", {}).get("last_medicine", "BP tablets")
        pharmacy = profile.get("memory", {}).get("preferred_pharmacy", "local pharmacy")
        task["title"] = f"Medicine refill: {last}"
        task["details"] = {"item": last, "from": pharmacy}
        task["parent_reply"] = (
            f"ശരി അമ്മേ, {last} {pharmacy}-ൽ നിന്ന് ഓർഡർ ചെയ്യാൻ തയ്യാറാക്കി. "
            "മകൻ/മകൾ അംഗീകരിച്ചാൽ ഉടൻ അറിയിക്കാം. ✅"
        )

    elif intent == "ride_booking":
        clinic = profile.get("memory", {}).get("regular_clinic", "clinic")
        when = f"{_find_day(text)} {_find_time(text) or ''}".strip()
        task["title"] = f"Ride to {clinic} ({when})"
        task["details"] = {"destination": clinic, "when": when}
        task["parent_reply"] = (
            f"ശരി, {when} {clinic}-ലേക്ക് വണ്ടി തയ്യാറാക്കി. "
            "അംഗീകാരം കിട്ടിയാൽ സമയം ഉറപ്പിച്ച് അറിയിക്കാം. 🚗"
        )

    elif intent == "reminder_request":
        task["title"] = "Reminder requested by parent"
        task["details"] = {"note": text}
        task["parent_reply"] = "ശരി അമ്മേ, ഓർമ്മപ്പെടുത്തൽ സെറ്റ് ചെയ്തു. 🔔"

    elif intent == "grocery_order":
        task["title"] = "Grocery / essentials order"
        task["details"] = {"note": text}
        task["parent_reply"] = (
            "ശരി അമ്മേ, ലിസ്റ്റ് തയ്യാറാക്കി. അംഗീകാരം കിട്ടിയാൽ ഓർഡർ ചെയ്യാം. 🛒"
        )

    elif intent == "checkin_reply":
        task["status"] = "logged"  # check-in, no approval needed
        task["title"] = f"Daily check-in OK — {parent}"
        task["parent_reply"] = "നന്നായി അമ്മേ, സന്തോഷം. ❤️ എന്തെങ്കിലും വേണമെങ്കിൽ പറയൂ."

    else:
        task["title"] = "Message for caregiver"
        task["details"] = {"note": text}
        task["parent_reply"] = "ശരി അമ്മേ, കുറിച്ച് വെച്ചു. വേറെ എന്തെങ്കിലും വേണോ?"

    return task


def todays_reminders(profile: dict) -> list[dict]:
    """Medicine reminders due today from the family profile."""
    out = []
    for med in profile.get("medicines", []):
        for slot in med.get("times", []):
            out.append({"type": "medicine", "time": slot,
                        "text": f"{med['name']} — {med.get('dose', '')} ({slot})"})
    return out


def weekly_summary(store_data: dict) -> str:
    """One calm summary for the child abroad, generated from logged data."""
    checkins = store_data.get("checkins", [])
    alerts = [a for a in store_data.get("alerts", [])]
    done = [t for t in store_data.get("tasks", []) if t.get("status") == "approved"]
    return (
        f"This week: {len(checkins)} daily check-in(s) received, "
        f"{len(done)} task(s) completed, {len(alerts)} emergency alert(s). "
        "Full details are on the dashboard."
    )


def llm_refine(text: str) -> str | None:
    """Optional future hook: plug Groq/Gemini free tier here. V1 runs without it."""
    if os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return None  # TODO V1.5: call the LLM to refine extraction
    return None
