"""Tests for V1.5 voice transcription. No API key, no network needed.
Run: python3 tests/test_voice.py"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import voice  # noqa: E402
import agent  # noqa: E402
import store  # noqa: E402

os.environ.pop("GROQ_API_KEY", None)


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    assert cond, name


# 1. No key -> clean refusal, no network call, typed text still the fallback
r = voice.transcribe_file("dummy.ogg")
check("no key refuses cleanly", r["ok"] is False and r["error"] == "no_key")
check("no key hint mentions free Groq key", "GROQ_API_KEY" in r["hint"])

# 2. Missing file -> clean error (with a dummy key, so the key check passes)
r = voice.transcribe_file("no-such-note.ogg", api_key="test-key")
check("missing file errors cleanly", r["ok"] is False and r["error"] == "no_file")

# 3. Bad model rejected before any network call
r = voice.transcribe_file("no-such-note.ogg", api_key="test-key", model="whisper-1")
check("bad model rejected", r["ok"] is False and r["error"] == "bad_model")

# 4. Multipart body is well-formed (boundary, model, language, file part)
open("/tmp/_amma_test.ogg", "wb").write(b"fake-audio-bytes")
body, boundary = voice._multipart_body("/tmp/_amma_test.ogg", "whisper-large-v3-turbo", "ml")
check("multipart has model", b'name="model"' in body and b"whisper-large-v3-turbo" in body)
check("multipart has language ml", b'name="language"' in body and b"\r\n\r\nml\r\n" in body)
check("multipart has file bytes", b"fake-audio-bytes" in body)
check("multipart ends with boundary", body.rstrip().endswith(f"--{boundary}--".encode()))

# 5. Mocked Groq success -> Malayalam transcript flows into the V1 agent brain
class FakeResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps({"text": "എന്റെ മരുന്ന് തീരാറായി", "language": "ml"}).encode()


real_urlopen = voice.urllib.request.urlopen
voice.urllib.request.urlopen = lambda req, timeout=60: FakeResp()
try:
    out = voice.voice_to_task("/tmp/_amma_test.ogg", store.DEFAULT_PROFILE, api_key="test-key")
finally:
    voice.urllib.request.urlopen = real_urlopen
check("mocked transcription ok", out["ok"] is True)
check("transcript kept", "മരുന്ന്" in out["transcript"])
check("transcript becomes refill task", out["task"]["intent"] == "medicine_refill")
check("refill still waits for approval", out["task"]["status"] == "pending_approval")

print("\nAll voice tests passed.")
