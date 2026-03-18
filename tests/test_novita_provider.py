from __future__ import annotations

import importlib


def reload_modules():
    config = importlib.import_module("app.core.config")
    providers = importlib.import_module("app.core.providers")
    return importlib.reload(config), importlib.reload(providers)


def clear_provider_env(monkeypatch):
    for key in (
        "PROVIDER_ORDER",
        "CHAT_PROVIDER",
        "EMBED_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_CHAT_MODEL",
        "OPENAI_EMBED_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_BASE_URL",
        "GEMINI_CHAT_MODEL",
        "GEMINI_EMBED_MODEL",
        "KIMI_API_KEY",
        "KIMI_BASE_URL",
        "KIMI_CHAT_MODEL",
        "KIMI_EMBED_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_CHAT_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_CHAT_MODEL",
        "NOVITA_API_KEY",
        "NOVITA_BASE_URL",
        "NOVITA_CHAT_MODEL",
        "NOVITA_EMBED_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_default_provider_order_includes_novita(monkeypatch):
    clear_provider_env(monkeypatch)

    config, _ = reload_modules()

    assert config.PROVIDER_ORDER == ["gemini", "deepseek", "openai", "novita", "kimi", "anthropic"]


def test_get_provider_builds_novita_provider_from_env(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("NOVITA_API_KEY", "novita-key")
    monkeypatch.setenv("NOVITA_BASE_URL", "https://api.novita.ai/openai")
    monkeypatch.setenv("NOVITA_CHAT_MODEL", "deepseek/deepseek-v3.2")
    monkeypatch.setenv("NOVITA_EMBED_MODEL", "novita-embed")

    _, providers = reload_modules()

    provider = providers.get_provider("novita")

    assert provider.name == "novita"
    assert provider.has_key() is True
    assert provider.base_url == "https://api.novita.ai/openai"
    assert provider.chat_model == "deepseek/deepseek-v3.2"
    assert provider.embed_model == "novita-embed"


def test_pick_provider_skips_novita_for_embeddings_without_embed_model(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("PROVIDER_ORDER", "novita,openai")
    monkeypatch.setenv("EMBED_PROVIDER", "auto")
    monkeypatch.setenv("NOVITA_API_KEY", "novita-key")
    monkeypatch.setenv("NOVITA_CHAT_MODEL", "deepseek/deepseek-v3.2")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    _, providers = reload_modules()

    provider = providers.pick_provider("embed")

    assert provider.name == "openai"
