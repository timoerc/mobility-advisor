"""Environment bootstrap shared by every entry point that talks to the LLM proxy.

Import this before anything that touches litellm/ADK's LiteLlm wrapper (agents/model.py,
api/app.py) — it points litellm's default OpenAI-compatible client at the KIConnect proxy
using the KICONNECT_API_KEY the rest of the app already requires, so no separate
OPENAI_API_KEY/OPENAI_API_BASE needs to be configured.
"""
import os

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("KICONNECT_API_KEY", ""))
os.environ.setdefault("OPENAI_API_BASE", "https://chat.kiconnect.nrw/api/v1")
