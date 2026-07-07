"""LLM wiring: OpenAI-compatible chat via LangChain, chain logic faked."""

import httpx
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from klams_mind.config import ModelConfig
from klams_mind.llm import build_chat, ping, resolve_model_name

# Recorded 2026-07-06 from live kai:8000/v1/models (trimmed).
MODELS_RESPONSE = {
    "object": "list",
    "data": [{"id": "gemma-4-31b-it-awq", "object": "model", "owned_by": "vllm"}],
}


def test_build_chat_points_at_configured_endpoint() -> None:
    cfg = ModelConfig(base_url="http://kai:8001/v1", name="test-model", api_key="k")

    chat = build_chat(cfg)

    assert chat.openai_api_base == "http://kai:8001/v1"
    assert chat.model_name == "test-model"


def test_ping_runs_prompt_through_model() -> None:
    fake = FakeListChatModel(responses=["pong"])

    assert ping(fake) == "pong"


async def test_resolve_model_name_auto_discovers_served_model() -> None:
    cfg = ModelConfig(base_url="http://kai:8000/v1", name="auto")
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=MODELS_RESPONSE))

    name = await resolve_model_name(cfg, http=httpx.AsyncClient(transport=transport))

    assert name == "gemma-4-31b-it-awq"


async def test_resolve_model_name_explicit_name_skips_discovery() -> None:
    cfg = ModelConfig(name="qwen3-8b-fp8")

    assert await resolve_model_name(cfg) == "qwen3-8b-fp8"
