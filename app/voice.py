"""V1.5 — Malayalam voice-note transcription for AmmaCare.

Parents send voice notes, not typed text. This module turns a voice-note
audio file into the text V1's agent brain already understands
(`agent.prepare_task`), so nothing in V1 changes.

₹0 path (recommended first): Groq Whisper, free tier, no card.
  - Models: whisper-large-v3-turbo ($0.04/audio-hour if ever paid) or
    whisper-large-v3. Both list Malayalam (`ml`) as supported.
  - Free tier (Groq rate-limits docs, checked 2026-11-12): 20 requests/min,
    2,000 requests/day, 7,200 audio seconds/hour, 28,800 audio seconds/day
    (8 hours/day), 25 MB max file. No card needed for the free plan; a free
    Groq API key is still required — sign up at console.groq.com, 5 minutes.
  - Accuracy caveat, from Whisper/Malayalam write-ups: Malayalam is
    "moderate" for Whisper — agglutinative, long compound words, limited
    training data. Short, clear voice notes work best. Manglish (Malayalam
    in Latin script) is code-mixed speech: pass language="ml" and expect
    Malayalam-script output, or leave language unset for auto-detect and
    check which comes back cleaner on real parent voice notes.

No-key / offline path: if GROQ_API_KEY is not set, transcription refuses
cleanly (no crash, no network call) and V1 keeps working on typed text.
Fully offline alternative, no key at all: run Whisper locally
(faster-whisper / whisper.cpp) — no monthly cap, audio never leaves the
machine, but it needs a model download (small models ~75 MB–1.5 GB;
large-v3 ~3 GB) and is slower on a laptop CPU. That is a later swap, not
a V1.5 blocker: this module is the single place to change.

Usage:
    export GROQ_API_KEY=...        # free Groq key, no card
    python3 -c "from app.voice import transcribe_file; print(transcribe_file('amma-note.ogg'))"
"""
import json
import mimetypes
import os
import uuid
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"
SUPPORTED_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")
MAX_FREE_FILE_BYTES = 25 * 1024 * 1024  # Groq free tier: 25 MB


def _multipart_body(path, model, language):
    """Build a multipart/form-data body with stdlib only. Returns (body, boundary)."""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(path)[0] or "audio/ogg"
    parts = []
    for name, value in (("model", model), ("language", language or "")):
        if not value:
            continue
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    with open(path, "rb") as f:
        audio = f.read()
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode() + audio + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def transcribe_file(path, api_key=None, model=DEFAULT_MODEL, language="ml"):
    """Transcribe one voice-note file. Returns a dict, never raises for
    expected failures (missing key / missing file / API error)."""
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        return {"ok": False, "error": "no_key",
                "hint": "Set GROQ_API_KEY (free Groq key, no card) to enable "
                        "voice notes. Typed Malayalam/Manglish still works without it."}
    if model not in SUPPORTED_MODELS:
        return {"ok": False, "error": "bad_model",
                "hint": f"Use one of {list(SUPPORTED_MODELS)}."}
    if not os.path.isfile(path):
        return {"ok": False, "error": "no_file", "hint": f"No audio file at {path}."}
    if os.path.getsize(path) > MAX_FREE_FILE_BYTES:
        return {"ok": False, "error": "too_large",
                "hint": "Groq free tier caps files at 25 MB — split the note first."}
    body, boundary = _multipart_body(path, model, language)
    req = urllib.request.Request(
        GROQ_URL, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # network / 429 / 401 — surface, don't crash the demo
        return {"ok": False, "error": "api_error", "hint": str(e)}
    text = (data.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "empty_transcript",
                "hint": "Whisper returned no text — try a clearer / longer note."}
    return {"ok": True, "text": text, "language": data.get("language", language),
            "model": model}


def voice_to_task(path, profile, api_key=None, language="ml"):
    """Voice note -> transcribed text -> V1 agent task. One call for the server
    to use later; keeps the approval-first rule (task is prepared, never executed)."""
    import agent  # local import: keeps voice.py importable standalone

    result = transcribe_file(path, api_key=api_key, language=language)
    if not result.get("ok"):
        return {"ok": False, **result}
    task = agent.prepare_task(result["text"], profile)
    return {"ok": True, "transcript": result["text"], "task": task}
