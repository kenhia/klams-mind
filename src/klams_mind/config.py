"""Configuration: homelab defaults ← TOML file ← environment overrides.

Default config path is ``~/.config/klams-mind/config.toml`` (override
with ``KLAMS_MIND_CONFIG``). Secrets (klams token) live there or in the
environment — never in the repo.
"""

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path("~/.config/klams-mind/config.toml")

# Env var → (section, field). KLAMS_URL/KLAMS_TOKEN match what the
# klams tooling already uses; the rest are klams-mind's own.
_ENV_OVERRIDES = {
    "KLAMS_URL": ("klams", "base_url"),
    "KLAMS_TOKEN": ("klams", "token"),
    "KLAMS_MIND_MODEL_URL": ("model", "base_url"),
    "KLAMS_MIND_MODEL_NAME": ("model", "name"),
    "KLAMS_MIND_MODEL_API_KEY": ("model", "api_key"),
}


class KlamsConfig(BaseModel):
    base_url: str = "http://kubs0:7777"
    token: str = ""


class ModelConfig(BaseModel):
    """An OpenAI-compatible chat endpoint (kvllm on kai by default)."""

    base_url: str = "http://kai:8000/v1"
    name: str = "auto"  # "auto" = discover the served model via /models
    api_key: str = "unused"  # vLLM ignores it; the client requires one


class Config(BaseModel):
    klams: KlamsConfig = KlamsConfig()
    model: ModelConfig = ModelConfig()


def load_config(
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> Config:
    """Load config; env/``.env`` overrides beat ``path`` beats
    ``KLAMS_MIND_CONFIG`` beats the homelab defaults. A missing file is
    fine.

    On the real-run path (``env`` unset) a ``./.env`` is auto-loaded so
    live runs pick up ``KLAMS_TOKEN`` without exporting it; the real
    environment still wins over ``.env``. Tests that inject ``env`` stay
    isolated — pass ``dotenv_path`` explicitly to exercise ``.env``.
    """
    autoload = env is None
    if env is None:
        env = os.environ
    if dotenv_path is None and autoload:
        dotenv_path = Path(".env")

    dotenv_map: dict[str, str] = {}
    if dotenv_path is not None and Path(dotenv_path).expanduser().is_file():
        dotenv_map = {k: v for k, v in dotenv_values(dotenv_path).items() if v is not None}
    effective = {**dotenv_map, **env}  # real env beats .env

    file = path or Path(effective.get("KLAMS_MIND_CONFIG", "") or DEFAULT_CONFIG_PATH)
    file = file.expanduser()

    data: dict[str, dict[str, str]] = {}
    if file.is_file():
        with file.open("rb") as fh:
            data = tomllib.load(fh)

    for var, (section, field) in _ENV_OVERRIDES.items():
        if var in effective:
            data.setdefault(section, {})[field] = effective[var]

    return Config.model_validate(data)
