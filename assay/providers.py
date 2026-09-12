"""One chat call, two providers, one shape.

Both providers speak the OpenAI chat-completions dialect with tools, so the runner
never branches on vendor. What differs is the base URL, the key, and what the usage
field carries:

- openrouter: `usage: {include: true}` makes OpenRouter return its own `cost` for the
  call. That number, and only that number, is what a receipt records as cost.
- gemini: Google's OpenAI-compatible endpoint returns token usage but no cost. The
  receipt records the tokens and says `cost_source = "not reported by provider"`. It
  does not look up a price table, because a price table is exactly the kind of number
  that turns a scoreboard into fiction.

Keys are read from `keys.local` (KEY=VALUE lines) beside the repo, or from the
environment. They are never logged. Gemini keys rotate on 429.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_KEYS: dict[str, str] | None = None


def _load_keys() -> dict[str, str]:
    global _KEYS
    if _KEYS is not None:
        return _KEYS
    keys: dict[str, str] = {}
    candidates = [Path.cwd() / "keys.local", Path(__file__).resolve().parents[1] / "keys.local"]
    for c in candidates:
        if c.exists():
            for raw in c.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip().strip('"').strip("'")
            break
    for k, v in os.environ.items():
        if k.startswith(("OPENROUTER_API_KEY", "GEMINI_API_KEY")) and v:
            keys.setdefault(k, v)
    _KEYS = keys
    return keys


class ProviderError(RuntimeError):
    """A transport-level failure: the request never produced a usable completion."""


class RateLimited(ProviderError):
    pass


@dataclass
class Completion:
    message: dict            # the assistant message: content, tool_calls
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cost_usd: float | None   # None when the provider does not report it
    cost_source: str
    latency_s: float
    raw: dict


PROVIDERS = {
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key_names": ["OPENROUTER_API_KEY"]},
    "gemini": {
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_names": [f"GEMINI_API_KEY_{i}" for i in range(1, 13)] + ["GEMINI_API_KEY"],
    },
}


def parse_model(spec: str) -> tuple[str, str]:
    """'openrouter:qwen/qwen3.7-flash' → ('openrouter', 'qwen/qwen3.7-flash'); bare ids default to openrouter."""
    if ":" in spec and spec.split(":", 1)[0] in PROVIDERS:
        p, m = spec.split(":", 1)
        return p, m
    return "openrouter", spec


def _post(url: str, key: str, payload: dict, timeout: int) -> tuple[dict, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/RabHanz/assay",
            "X-Title": "assay",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace")), dict(r.headers)


def chat(provider: str, model: str, messages: list, tools: list, max_tokens: int,
         timeout: int = 300) -> Completion:
    cfg = PROVIDERS[provider]
    keys = _load_keys()
    names = [n for n in cfg["key_names"] if keys.get(n)]
    if not names:
        raise ProviderError(f"no key for provider {provider} (expected one of {cfg['key_names'][:2]}…) in keys.local")
    payload: dict = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": int(max_tokens),
    }
    if provider == "openrouter":
        payload["usage"] = {"include": True}

    last_err: Exception | None = None
    t0 = time.time()
    for attempt, name in enumerate(names):
        try:
            data, _headers = _post(cfg["base"] + "/chat/completions", keys[name], payload, timeout)
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429 and provider == "gemini" and attempt < len(names) - 1:
                last_err = RateLimited(f"429 on key {name}; rotating")
                continue
            if e.code == 429:
                raise RateLimited(f"429 from {provider}: {body}") from None
            raise ProviderError(f"HTTP {e.code} from {provider}: {body}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"{type(e).__name__} from {provider}: {str(e)[:200]}") from None
    else:
        raise last_err or ProviderError("no attempt made")
    latency = time.time() - t0

    if "choices" not in data or not data["choices"]:
        err = data.get("error") or data
        raise ProviderError(f"{provider} returned no choices: {json.dumps(err)[:300]}")
    choice = data["choices"][0]
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    cost = usage.get("cost") if provider == "openrouter" else None
    return Completion(
        message=choice.get("message") or {},
        finish_reason=choice.get("finish_reason"),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        reasoning_tokens=int(details.get("reasoning_tokens") or 0),
        cost_usd=float(cost) if cost is not None else None,
        cost_source="provider usage field" if cost is not None else "not reported by provider",
        latency_s=latency,
        raw=data,
    )
