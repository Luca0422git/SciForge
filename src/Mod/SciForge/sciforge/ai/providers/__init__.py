# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI providers the built-in chat panel can talk to, one adapter per API
(docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.5).

Every adapter has the same methods, so the chat loop (sciforge/ai/chat_core.py) does not
care which one it drives:
  build_request(model, system, messages, tools, max_tokens, key, base_url)
      -> (url, headers, body)      tools: tools_core.TOOLS, translated for that API
  parse_response(body) -> {"text", "tool_calls": [{"id", "name", "args"}], "stop":
      "end" | "tool_use" | "max_tokens" | "refusal" | other, "usage", "progress", "raw"}
  tool_results_message([(call, result), ...]) -> the API's message(s) with the results
  to_provider_messages(history, model) -> the neutral history in that API's words
  list_models(key, base_url) -> model ids from the provider's models endpoint ([] on errors)
  key_refused(status, body) -> True when the answer means "this key is not accepted"

Each module keeps its one DEFAULT_MODEL; nothing else names models.
"""

from . import anthropic, gemini, openai, openai_compat

ORDER = ("anthropic", "openai", "gemini", "openai_compat")

_MODULES = {
    "anthropic": anthropic,
    "openai": openai,
    "gemini": gemini,
    "openai_compat": openai_compat,
}

PROVIDERS = {
    name: {
        "name": name,
        "display_name": module.DISPLAY_NAME,
        "needs_key": module.NEEDS_KEY,
        "base_url": module.BASE_URL,
        "default_model": module.DEFAULT_MODEL,
        "supports_images": module.SUPPORTS_IMAGES,
        "module": module,
    }
    for name, module in _MODULES.items()
}

# The two local servers people use most, for the "Local or other" choice.
LOCAL_SERVERS = (
    ("Ollama", openai_compat.BASE_URL),
    ("LM Studio", openai_compat.LM_STUDIO_URL),
)


def get(name):
    """The provider's entry (a dict, see PROVIDERS), or None for an unknown name."""
    return PROVIDERS.get(name)


def adapter(name):
    """A new Adapter for this provider, or None."""
    entry = PROVIDERS.get(name)
    return entry["module"].Adapter() if entry else None


def default_model(name, key=None, base_url=None, models=None):
    """The model to preselect: the provider's DEFAULT_MODEL, or for a provider without one
    (a local server) the first model it lists. models: an already fetched list."""
    entry = PROVIDERS.get(name)
    if entry is None:
        return ""
    if entry["default_model"]:
        return entry["default_model"]
    if models is None:
        models = adapter(name).list_models(key, base_url or entry["base_url"])
    return models[0] if models else ""
