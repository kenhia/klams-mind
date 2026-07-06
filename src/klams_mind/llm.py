"""Model access via LangChain over OpenAI-compatible endpoints (kvllm).

No in-process model loading — everything goes over HTTP to whatever
the config points at.
"""

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from klams_mind.config import ModelConfig

_PING_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You answer with a single word and nothing else."),
        ("human", "Say the word: {word}"),
    ]
)


def build_chat(cfg: ModelConfig) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=cfg.base_url,
        api_key=SecretStr(cfg.api_key),
        model=cfg.name,
        temperature=0,
    )


def ping(model: BaseChatModel, word: str = "pong") -> str:
    """Trivial chain proving the endpoint is alive and following prompts."""
    chain = _PING_PROMPT | model | StrOutputParser()
    return chain.invoke({"word": word}).strip()


async def resolve_model_name(cfg: ModelConfig, http: httpx.AsyncClient | None = None) -> str:
    """Resolve "auto" to whatever the endpoint is actually serving.

    kvllm serves one model at a time and switches by registry key, so
    asking `/models` beats hardcoding a name that goes stale.
    """
    if cfg.name != "auto":
        return cfg.name
    url = f"{cfg.base_url}/models"
    if http is not None:
        resp = await http.get(url)
    else:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
    resp.raise_for_status()
    served = resp.json()["data"]
    if not served:
        raise RuntimeError(f"no models served at {url}")
    return served[0]["id"]
