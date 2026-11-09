"""Local, free LLMs only (Ollama or LM Studio) for the DASHX story writer.

VENDORED from purffle-shorts (MIT). Removed: every paid or key-based provider (OpenAI, Claude, Gemini,
Groq, OpenRouter, DeepSeek, Mistral, Together, xAI) and the native Anthropic client, so the story
writer can never ask for an API key or send text to a cloud service.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .utils import PermanentError, http, raise_for_status, with_retries

log = logging.getLogger("purffle")


class LLMError(RuntimeError):
    pass


class LLMConfigError(LLMError):
    """Missing key, unknown provider, etc. — stop instead of retrying every video."""


@dataclass(frozen=True)
class Preset:
    name: str
    label: str
    base_url: str
    key_envs: tuple[str, ...]
    default_model: str
    kind: str = "openai"          # openai (chat/completions compatible) | anthropic
    json_mode: bool = True        # supports response_format={"type":"json_object"}
    local: bool = False
    schema_mode: bool = False     # supports strict response_format={"type":"json_schema"} (exact keys and types)


PRESETS: dict[str, Preset] = {p.name: p for p in [
    Preset("ollama", "Ollama (local, free)", "http://localhost:11434/v1", (), "llama3.2", local=True,
           schema_mode=True),
    Preset("lmstudio", "LM Studio (local, free)", "http://localhost:1234/v1", (), "local-model",
           json_mode=False, local=True, schema_mode=True),
]}

AUTO_ORDER: list[str] = []  # no key-based providers in this copy

def _key_for(preset: Preset, settings: Settings) -> str:
    if preset.name == "custom":
        return settings.llm_api_key
    for env in preset.key_envs:
        if os.getenv(env):
            return os.environ[env]
    return settings.llm_api_key if preset.name == settings.llm_provider else ""


def _ollama_up(base_url: str) -> bool:
    try:
        root = base_url.rsplit("/v1", 1)[0]
        return http().get(root + "/api/tags", timeout=1.5).ok
    except Exception:
        return False


def ollama_url() -> str:
    host = os.getenv("OLLAMA_HOST", "").rstrip("/") or PRESETS["ollama"].base_url
    if not host.startswith("http"):
        host = "http://" + host
    return host if host.endswith("/v1") else host + "/v1"


def ollama_models(base_url: str) -> list[str] | None:
    """Models pulled into Ollama, or None when Ollama is not reachable."""
    try:
        r = http().get(base_url.rsplit("/v1", 1)[0] + "/api/tags", timeout=1.5)
        return [m.get("name", "") for m in r.json().get("models", [])] if r.ok else None
    except Exception:
        return None


def ollama_has(installed: list[str], model: str) -> bool:
    return model in installed or (":" not in model and f"{model}:latest" in installed)


def available_providers(settings: Settings) -> list[str]:
    """Providers that have credentials configured (in auto order)."""
    return [n for n in AUTO_ORDER if _key_for(PRESETS[n], settings)]


def resolve_provider_name(settings: Settings) -> str:
    name = settings.llm_provider or "auto"
    if name != "auto":
        if name not in PRESETS:
            raise LLMConfigError(f"Unknown LLM_PROVIDER '{name}'. Choose one of: {', '.join(PRESETS)}")
        return name
    if settings.llm_base_url:
        return "custom"
    found = available_providers(settings)
    if found:
        return found[0]
    if _ollama_up(ollama_url()):
        return "ollama"
    raise LLMConfigError(
        "No local LLM found. Start Ollama (ollama serve) and pull a model (ollama pull <model>). "
        "This copy only supports free local models."
    )


def extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object out of a model reply that may include code fences or chatter."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I | re.S).strip()
    try:
        val = json.loads(t)
        if isinstance(val, dict):
            return val
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        chunk = t[start:end + 1]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            # Trailing commas are the most common model mistake.
            return json.loads(re.sub(r",\s*([}\]])", r"\1", chunk))
    raise LLMError(f"Model did not return JSON: {text[:200]!r}")


class Provider:
    name: str = ""
    model: str = ""

    def complete(self, system: str, user: str, *, schema: dict | None = None,
                 temperature: float = 0.9, max_tokens: int = 4000) -> str:
        raise NotImplementedError

    def __str__(self) -> str:
        return f"{self.name}:{self.model}"


class OpenAICompatible(Provider):
    def __init__(self, preset: Preset, model: str, api_key: str, base_url: str):
        self.name, self.preset, self.model = preset.name, preset, model
        self.api_key, self.base_url = api_key, base_url.rstrip("/")
        self._json_mode = preset.json_mode
        self._schema_mode = preset.schema_mode and os.getenv("LLM_JSON_SCHEMA", "true").lower() not in ("0", "false")

    def _is_reasoning_model(self) -> bool:
        return bool(re.match(r"^(o\d|gpt-5)", self.model.split("/")[-1]))

    def complete(self, system, user, *, schema=None, temperature=0.9, max_tokens=4000) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self._is_reasoning_model():
            payload["max_completion_tokens"] = max(max_tokens, 8000)  # room for hidden reasoning tokens
        else:
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens
        if schema and self._schema_mode:
            # Strict structured output: the reply is guaranteed to have exactly the keys and types asked for.
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "reply", "schema": schema, "strict": True}}
        elif schema is not None and self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            # A local model on a laptop CPU can take minutes for one script; cloud APIs answer far sooner.
            timeout = 600 if self.preset.local else 180
            r = http().post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=timeout)
            raise_for_status(r, f"{self}")
        except PermanentError as e:
            fmt = payload.get("response_format", {}).get("type")
            text = str(e).lower()
            named = any(k in text for k in ("response_format", "json_schema", "schema", "structured"))
            # Strict schemas are newer: a plain "bad request" from an endpoint in that mode is worth one retry
            # without it (an auth error would fail the same way and is reported as such).
            generic = fmt == "json_schema" and ("http 400" in text or "http 422" in text)
            if fmt and (named or generic):
                # The endpoint (or this model) can't do it: step down to JSON mode, then to prompt + parser.
                if fmt == "json_schema":
                    self._schema_mode = False
                    log.info("%s: no strict JSON schema support; using JSON mode", self)
                else:
                    self._json_mode = False
                return self.complete(system, user, schema=schema, temperature=temperature, max_tokens=max_tokens)
            raise
        data = r.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"{self}: unexpected response {str(data)[:200]}") from e
        if not content:
            raise LLMError(f"{self}: empty reply (finish_reason={data['choices'][0].get('finish_reason')})")
        return content


def build_provider(name: str, settings: Settings, model: str = "") -> Provider:
    preset = PRESETS[name]
    chosen = model
    model = model or preset.default_model
    key = _key_for(preset, settings)
    base_url = preset.base_url
    if name == "custom":
        base_url = settings.llm_base_url
        if not base_url or not model:
            raise LLMConfigError("LLM_PROVIDER=custom needs LLM_BASE_URL and LLM_MODEL")
    elif name == "ollama":
        base_url = ollama_url()
        installed = None if chosen else ollama_models(base_url)
        if installed and not ollama_has(installed, model):
            # No model chosen and the default is not pulled: use one that is, instead of failing every video.
            log.info("Ollama has no '%s'; using installed model '%s' (set LLM_MODEL to choose)", model, installed[0])
            model = installed[0]
    if settings.llm_base_url and name == settings.llm_provider:
        base_url = settings.llm_base_url
    if not key and not preset.local and name != "custom":
        raise LLMConfigError(f"{preset.label}: set {' or '.join(preset.key_envs)} in .env")
    return OpenAICompatible(preset, model, key, base_url)


class LLM:
    """Primary provider + ordered fallbacks. ``complete_json`` returns a parsed dict."""

    def __init__(self, settings: Settings):
        self.settings = settings
        primary = resolve_provider_name(settings)
        names = [primary] + [n for n in settings.llm_fallbacks if n != primary]
        self.providers: list[Provider] = []
        for n in names:
            if n not in PRESETS:
                log.warning("Ignoring unknown LLM fallback '%s'", n)
                continue
            try:
                self.providers.append(build_provider(n, settings, settings.llm_model if n == primary else ""))
            except LLMError as e:
                if n == primary:
                    raise
                log.warning("Skipping fallback %s: %s", n, e)

    @property
    def label(self) -> str:
        return str(self.providers[0])

    def complete_json(self, system: str, user: str, schema: dict | None = None,
                      max_tokens: int = 4000, temperature: float | None = None) -> dict[str, Any]:
        """``temperature`` overrides LLM_TEMPERATURE for this call (low for grading, where repeatability matters)."""
        errors = []
        temp = self.settings.llm_temperature if temperature is None else temperature
        for p in self.providers:
            def _call(p=p):
                text = p.complete(system, user, schema=schema if schema is not None else {}, max_tokens=max_tokens,
                                  temperature=temp)
                return extract_json(text)
            try:
                result = with_retries(_call, attempts=2, base_delay=3, label=f"LLM {p}")
                if p is not self.providers[0]:
                    log.info("Used fallback LLM %s", p)
                return result
            except Exception as e:  # try the next provider
                errors.append(f"{p}: {e}")
                log.warning("LLM %s failed: %s", p, e)
        raise LLMError("All LLM providers failed:\n  " + "\n  ".join(errors))
