"""Config loading: TOML file + environment overrides."""

from pathlib import Path

from klams_mind.config import Config, load_config

FULL_TOML = """\
[klams]
base_url = "http://kubs0:7777"
token = "km-secret"

[model]
base_url = "http://kai:8001/v1"
name = "test-model"
api_key = "unused"
"""


def test_load_from_toml(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(FULL_TOML)

    cfg = load_config(path=cfg_file, env={})

    assert cfg.klams.base_url == "http://kubs0:7777"
    assert cfg.klams.token == "km-secret"
    assert cfg.model.base_url == "http://kai:8001/v1"
    assert cfg.model.name == "test-model"
    assert cfg.model.api_key == "unused"


def test_env_overrides_beat_toml(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(FULL_TOML)

    cfg = load_config(
        path=cfg_file,
        env={
            "KLAMS_URL": "http://localhost:9999",
            "KLAMS_TOKEN": "env-token",
            "KLAMS_MIND_MODEL_URL": "http://localhost:8123/v1",
            "KLAMS_MIND_MODEL_NAME": "other-model",
            "KLAMS_MIND_MODEL_API_KEY": "env-key",
        },
    )

    assert cfg.klams.base_url == "http://localhost:9999"
    assert cfg.klams.token == "env-token"
    assert cfg.model.base_url == "http://localhost:8123/v1"
    assert cfg.model.name == "other-model"
    assert cfg.model.api_key == "env-key"


def test_no_file_yields_homelab_defaults() -> None:
    """Zero config works on the homelab: defaults point at kubs0/kai."""
    cfg = load_config(path=None, env={"KLAMS_MIND_CONFIG": "/nonexistent"})

    assert isinstance(cfg, Config)
    assert "kubs0" in cfg.klams.base_url
    assert cfg.klams.token == ""
    assert cfg.model.base_url.endswith("/v1")
    assert cfg.model.name  # some non-empty default


def test_env_config_path_is_respected(tmp_path: Path) -> None:
    cfg_file = tmp_path / "elsewhere.toml"
    cfg_file.write_text(FULL_TOML)

    cfg = load_config(path=None, env={"KLAMS_MIND_CONFIG": str(cfg_file)})

    assert cfg.klams.token == "km-secret"


def test_partial_toml_keeps_defaults(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[klams]\ntoken = "just-a-token"\n')

    cfg = load_config(path=cfg_file, env={})

    assert cfg.klams.token == "just-a-token"
    assert "kubs0" in cfg.klams.base_url  # default retained


def test_dotenv_supplies_env_overrides(tmp_path: Path) -> None:
    """A `.env` file feeds the same override vars as the real environment."""
    envfile = tmp_path / ".env"
    envfile.write_text("KLAMS_TOKEN=from-dotenv\n")

    cfg = load_config(path=None, env={}, dotenv_path=envfile)

    assert cfg.klams.token == "from-dotenv"


def test_real_env_beats_dotenv(tmp_path: Path) -> None:
    envfile = tmp_path / ".env"
    envfile.write_text("KLAMS_TOKEN=from-dotenv\n")

    cfg = load_config(path=None, env={"KLAMS_TOKEN": "from-env"}, dotenv_path=envfile)

    assert cfg.klams.token == "from-env"


def test_injected_env_does_not_autoload_dotenv(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Tests that inject `env` stay isolated from any real ./.env in cwd."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("KLAMS_TOKEN=leaked\n")

    cfg = load_config(path=None, env={})

    assert cfg.klams.token == ""  # ./.env not auto-loaded when env is injected
