"""Small shared helpers: retries, HTTP, slugs, text cleanup."""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import json as _json
import urllib.error
import urllib.request

log = logging.getLogger("purffle")

T = TypeVar("T")

USER_AGENT = "PurffleShorts-vendored (local Ollama only)"


class PermanentError(Exception):
    """An error that retrying will not fix (bad key, 4xx, invalid input)."""


class Cancelled(Exception):
    """The user stopped the job (Studio "Cancel"): raised at the next stage boundary or ffmpeg step."""


# Set by the Studio to stop the running job. Jobs run one at a time, so one flag for the process is enough.
CANCEL = threading.Event()


def check_cancel() -> None:
    if CANCEL.is_set():
        raise Cancelled("cancelled")


def emphasis_key(word: str) -> str:
    """How a caption word is compared for highlighting: lower case, without the punctuation around it."""
    return re.sub(r"^\W+|\W+$", "", word.lower(), flags=re.UNICODE)


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 2.0,
    label: str = "operation",
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call ``fn`` with exponential backoff + jitter. PermanentError is never retried."""
    for i in range(1, attempts + 1):
        try:
            return fn()
        except PermanentError:
            raise
        except retry_on as e:
            if i == attempts:
                log.error("%s failed after %d attempts: %s", label, attempts, redact(e))
                raise
            wait = base_delay * (2 ** (i - 1)) + random.uniform(0, 0.5)
            log.warning("%s attempt %d/%d failed: %s — retrying in %.1fs", label, i, attempts, redact(e), wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


class _Response:
    """Minimal stand-in for ``requests.Response`` (status_code, ok, text, json())."""

    def __init__(self, status_code: int, text: str):
        self.status_code, self.text = status_code, text

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self):
        return _json.loads(self.text)


class _Http:
    """Tiny urllib-based HTTP client. Only used to talk to a local Ollama / LM Studio server,
    so the original ``requests`` dependency is not needed."""

    def _send(self, method: str, url: str, *, json=None, headers=None, timeout: float = 30) -> _Response:
        data = _json.dumps(json).encode("utf-8") if json is not None else None
        h = {"User-Agent": USER_AGENT, **(headers or {})}
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return _Response(r.status, r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            return _Response(e.code, e.read().decode("utf-8", errors="replace"))

    def get(self, url: str, *, headers=None, timeout: float = 30) -> _Response:
        return self._send("GET", url, headers=headers, timeout=timeout)

    def post(self, url: str, *, json=None, headers=None, timeout: float = 30) -> _Response:
        return self._send("POST", url, json=json, headers=headers, timeout=timeout)


_session: _Http | None = None


def http() -> _Http:
    """A shared HTTP client."""
    global _session
    if _session is None:
        _session = _Http()
    return _session


def raise_for_status(resp: _Response, what: str) -> None:
    """Raise PermanentError for 4xx (except 408/429) and a retryable error otherwise."""
    if resp.status_code < 400:
        return
    body = resp.text[:300].replace("\n", " ")
    msg = f"{what}: HTTP {resp.status_code} — {body}"
    if 400 <= resp.status_code < 500 and resp.status_code not in (408, 409, 429):
        raise PermanentError(msg)
    raise RuntimeError(msg)


_SECRET_RE = re.compile(r"(?i)\b((?:api_?)?key|token|access_token)=[^&\s'\"]+")
# Some services echo your IP in error bodies (e.g. "Queue full for IP: ..."); logs get pasted into issues.
_IP_RE = re.compile(r"(?i)(?<![\w:.])(?:(?:[0-9a-f]{1,4}:){4,7}[0-9a-f]{1,4}|(?:\d{1,3}\.){3}\d{1,3})(?![\w:.])")


# Webhook URLs carry their secret in the path.
_HOOK_RE = re.compile(r"(?i)(/api/webhooks/\d+/|hooks\.slack\.com/services/)[\w/-]+")


def redact(text: object) -> str:
    """Hide API keys that some services (e.g. Pixabay) put in URLs, webhook tokens and IP addresses
    before they reach a log."""
    t = _HOOK_RE.sub(r"\1***", _SECRET_RE.sub(r"\1=***", str(text)))
    return _IP_RE.sub("<ip>", t)


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].rstrip("-")) or "short"


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0000FE0F\U0000200D\U00002190-\U000021FF\U00002B00-\U00002BFF]+"
)


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def clean_narration(text: str) -> str:
    """Remove things a TTS voice should never read aloud: stage directions, labels, emoji, hashtags, markdown."""
    t = strip_emoji(text)
    t = re.sub(r"\[[^\]]*\]", " ", t)                      # [Hook], [Music]
    t = re.sub(r"\((?:pause|beat|music|sfx|laughs?)[^)]*\)", " ", t, flags=re.I)
    t = re.sub(r"^\s*(?:narrator|voice ?over|vo|host|scene \d+|hook|cta)\s*:\s*", "", t, flags=re.I | re.M)
    t = re.sub(r"(?<!\w)#\w+", " ", t)                     # hashtags
    t = re.sub(r"[*_`~>|]+", " ", t)                        # markdown
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\s*[—–]\s*", ", ", t)   # dashes read better as pauses ("copper — not iron" -> "copper, not iron")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)  # no space before punctuation
    t = re.sub(r",\s*([,.!?;:])", r"\1", t)  # "blue, ." -> "blue."
    return t


def truncate_words(text: str, limit: int) -> str:
    """Trim to ``limit`` characters on a word boundary."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return cut or text[:limit]
