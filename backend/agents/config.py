"""Portkey / model configuration.

Every agent on the team uses exactly one model: gpt-6-luna through Portkey. There is no
override (no env var, no request field) so nothing else can sneak into a run.

The key is read from PORTKEY_API_KEY in a .env in hw5/ or any parent folder (nearest wins).
It is never logged or sent to the dashboard.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

HW5_ROOT = Path(__file__).resolve().parents[2]
for folder in [HW5_ROOT, *HW5_ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Put it in a .env in hw5/ or a parent folder.")
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    client = AsyncOpenAI(
        api_key=require_api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
