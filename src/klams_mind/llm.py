"""Model access via LangChain over OpenAI-compatible endpoints (kvllm).

The client mechanics live in kvllm-client (the kvllm repo's client/
distribution — homelab-ai WI 274); this module keeps klams-mind's
config-shaped seam over it. No in-process model loading — everything
goes over HTTP to whatever the config points at.
"""

import httpx
import kvllm_client
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from klams_mind.config import ModelConfig

_PING_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You answer with a single word and nothing else."),
        ("human", "Say the word: {word}"),
    ]
)


def build_chat(cfg: ModelConfig) -> ChatOpenAI:
    chat, _ = kvllm_client.local_model(cfg.base_url, model=cfg.name, api_key=cfg.api_key)
    return chat


def ping(model: BaseChatModel, word: str = "pong") -> str:
    """Trivial chain proving the endpoint is alive and following prompts."""
    chain = _PING_PROMPT | model | StrOutputParser()
    return chain.invoke({"word": word}).strip()


async def resolve_model_name(cfg: ModelConfig, http: httpx.AsyncClient | None = None) -> str:
    """Resolve "auto" to whatever the endpoint is actually serving.

    kvllm serves one model at a time and switches by registry key, so
    asking `/models` beats hardcoding a name that goes stale.
    """
    return await kvllm_client.aresolve_model(cfg.name, cfg.base_url, http=http)
