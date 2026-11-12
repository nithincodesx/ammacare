"""AmmaCare demo server — Python stdlib only. Run: python3 app/server.py"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(__file__))
import agent  # noqa: E402
import store  # noqa: E402

STATIC = os.path.join(os.path.dirname(__file__), "static", "index.html")
_next_id = [1000]


def _id() -> int:
    _next_id[0] += 1
    return _next_id[0]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep console quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(STATIC, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = store.load()
        if self.path == "/api/state":
            self._json({
                "profile": data["profile"],
                "messages": data["messages"],
                "tasks": data["tasks"],
                "alerts": data["alerts"],
                "checkins": data["checkins"],
                "reminders": agent.todays_reminders(data["profile"]),
                "summary": agent.weekly_summary(data),
            })
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        data = store.load()

        if self.path == "/api/message":  # parent sends a message
            text = (payload.get("text") or "").strip()
            if not text:
                return self._json({"error": "empty"}, 400)
            task = agent.prepare_task(text, data["profile"])
            data["messages"].append({"from": "parent", "text": text, "at": store.now()})
            data["messages"].append({"from": "agent", "text": task["parent_reply"], "at": store.now()})
            result = {"intent": task["intent"]}
            if task["intent"] == "emergency":
                alert = {"id": _id(), "at": store.now(), "text": text,
                         "title": task["title"]}
                data["alerts"].append(alert)
                result["alert"] = alert
            elif task["status"] == "logged":
                data["checkins"].append({"at": store.now(), "text": text})
            else:
                task["id"] = _id()
                task["at"] = store.now()
                data["tasks"].append(task)
                result["task"] = task
            store.save(data)
            return self._json(result)

        if self.path == "/api/task/decision":  # caregiver approves / cancels
            tid, decision = payload.get("id"), payload.get("decision")
            for t in data["tasks"]:
                if t.get("id") == tid:
                    t["status"] = "approved" if decision == "approve" else "cancelled"
                    note = ("✅ അംഗീകരിച്ചു: " + t["title"]) if decision == "approve" \
                        else ("❌ റദ്ദാക്കി: " + t["title"] + " — മകൻ/മകൾ നേരിട്ട് വിളിക്കും.")
                    data["messages"].append({"from": "agent", "text": note, "at": store.now()})
                    store.save(data)
                    return self._json({"ok": True, "task": t})
            return self._json({"error": "task not found"}, 404)

        if self.path == "/api/reset":
            if os.path.exists(os.path.join(os.path.dirname(__file__), "..", "data.json")):
                os.remove(os.path.join(os.path.dirname(__file__), "..", "data.json"))
            store.load()
            return self._json({"ok": True})

        self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print(f"AmmaCare demo running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
