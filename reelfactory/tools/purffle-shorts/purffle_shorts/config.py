"""Settings for the DASHX story writer.

VENDORED from purffle-shorts (MIT), cut down to what the script writer needs (LLM choice, language,
length, Script Doctor). All upload / publishing / TikTok / Instagram / webhook settings and the
``.env`` loading were removed: there is no setting here that can post anything or hold an API key.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class ConfigError(ValueError):
    pass


@dataclass
class Settings:
    # --- what we write ---------------------------------------------------------------------
    niches: list[str] = field(default_factory=lambda: ["gali cricket stories for kids"])
    style: str = "story"
    language: str = "hi"
    target_seconds: int = 25
    audience: str = "kids and families in India who play gali cricket"
    trends_geo: str = "IN"
    seo_keywords: bool = False       # YouTube search lookups are removed
    offline: bool = False

    # --- LLM (local only) --------------------------------------------------------------------
    llm_provider: str = "ollama"
    llm_model: str = ""              # blank = first model installed in Ollama
    llm_base_url: str = ""
    llm_api_key: str = ""            # never used for local models
    llm_fallbacks: list[str] = field(default_factory=list)
    llm_temperature: float = 0.8
    anthropic_effort: str = ""       # unused, kept so llm.py's Settings access still works
    script_review: str = "rewrite"   # off|score|rewrite: the Script Doctor's second pass
    script_review_rounds: int = 1
    script_target_score: int = 80

    # --- extra rules for the idea planner (added by our adapter) -----------------------------
    planner_rules: str = ""
