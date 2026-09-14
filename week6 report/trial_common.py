"""Standard-library Lumid client; no files, redirects, retries or secret output."""
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def credential():
    token = os.environ.get("LUMID_PAT", "")
    if not token and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "LUMID_PAT":
                token = value.strip().strip(chr(34)).strip(chr(39))
                break
    if not token:
        raise RuntimeError("Set LUMID_PAT in the environment or repository .env")
    return token

def request(url, payload=None, *, token=None):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "lum.id" or parsed.username:
        raise ValueError("Only https://lum.id is allowed")
    token = token or credential()
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=body, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(req, timeout=60) as response:
            raw = response.read()
        if token.encode() in raw:
            raise ValueError("Credential-bearing response")
        return raw
    except Exception:
        raise RuntimeError("Lumid request failed; response details suppressed") from None

def chat(model, prompt, *, max_tokens=600, thinking=False):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": max_tokens,
               "chat_template_kwargs": {"enable_thinking": thinking}}
    result = {"model": model, "requested_at": datetime.now(timezone.utc).isoformat(),
              "request_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}
    start = time.perf_counter()
    try:
        raw = request("https://lum.id/llm/v1/chat/completions", payload)
        response = json.loads(raw)
        usage = response.get("usage", {})
        choice = response["choices"][0]
        result.update(total_tokens=usage.get("total_tokens"), usage=usage,
                      finish_reason=choice.get("finish_reason"),
                      response_sha256=hashlib.sha256(raw).hexdigest())
        result["answer"] = json.loads(choice["message"].get("content") or "")
    except Exception:
        result.update(answer=None, error="Request failed or no JSON answer; attempt retained")
    result["seconds"] = round(time.perf_counter() - start, 3)
    return result

def show(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))
