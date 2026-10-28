"""Loopback OpenAI-compatible provider that records every request. No network, no real keys."""
import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeProvider:
    def __init__(self, replies=None):
        self.requests, self._replies, self._lock = [], list(replies or []), threading.Lock()
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _send(self, code, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code); self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                self._send(200, {"object": "list", "data": [{"id": "fake-model", "object": "model"}]})
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                with outer._lock:
                    outer.requests.append({"path": self.path, "body": body})
                    reply = outer._replies.pop(0) if (body.get("tools") and outer._replies) else "ok"
                msg = {"role": "assistant", "content": reply} if isinstance(reply, str) else \
                      {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function",
                       "function": {"name": reply["tool"], "arguments": json.dumps(reply["args"])}}]}
                if body.get("stream"):
                    d = {"content": msg["content"]} if isinstance(reply, str) else \
                        {"tool_calls": [{"index": 0, **msg["tool_calls"][0]}]}
                    fin = "stop" if isinstance(reply, str) else "tool_calls"
                    ev = [{"choices": [{"index": 0, "delta": {"role": "assistant", **d}}]},
                          {"choices": [{"index": 0, "delta": {}, "finish_reason": fin}],
                           "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}]
                    out = "".join(f"data: {json.dumps({'id': 'x', 'object': 'chat.completion.chunk', 'model': 'fake-model', **e})}\n\n" for e in ev) + "data: [DONE]\n\n"
                    self._send(200, out.encode(), "text/event-stream")
                else:
                    fin = "stop" if isinstance(reply, str) else "tool_calls"
                    self._send(200, {"id": "x", "object": "chat.completion", "model": "fake-model",
                                     "choices": [{"index": 0, "message": msg, "finish_reason": fin}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base_url = f"http://127.0.0.1:{self._srv.server_address[1]}/v1"

    def __enter__(self):
        threading.Thread(target=self._srv.serve_forever, daemon=True).start(); return self
    def __exit__(self, *a):
        self._srv.shutdown(); self._srv.server_close()

    def main_requests(self):
        return [r for r in self.requests if r["body"].get("tools")]
    def aux_requests(self):
        return [r for r in self.requests if not r["body"].get("tools")]
