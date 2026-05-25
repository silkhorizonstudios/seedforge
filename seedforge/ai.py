"""AI-слой: мульти-провайдерная генерация контекстно-зависимых тестовых данных.

Поддерживаемые провайдеры:
- Anthropic (Claude)
- OpenAI (GPT-4o, GPT-4o-mini)
- Google Gemini
- Groq (Llama, Mixtral)
- Ollama (локальные модели)

Отправляет только метаданные схемы (имена таблиц/колонок), НЕ реальные данные.
"""

import json
import os
from typing import Protocol


# --- Провайдеры ---

class AIProvider(Protocol):
    def generate(self, prompt: str, max_tokens: int) -> str: ...


class AnthropicProvider:
    name = "Anthropic (Claude)"
    env_key = "ANTHROPIC_API_KEY"

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 8192) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


class OpenAIProvider:
    name = "OpenAI (GPT)"
    env_key = "OPENAI_API_KEY"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 8192) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


class GeminiProvider:
    name = "Google Gemini"
    env_key = "GEMINI_API_KEY"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 8192) -> str:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]


class GroqProvider:
    name = "Groq"
    env_key = "GROQ_API_KEY"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 8192) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


# Реестр провайдеров: ключ → (класс, env_var)
PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
}


def detect_provider(api_key: str | None = None, provider: str | None = None) -> AIProvider | None:
    """Автоматически определить провайдера по ключу или env."""
    # Явно указан провайдер
    if provider and provider in PROVIDERS:
        cls = PROVIDERS[provider]
        key = api_key or os.environ.get(cls.env_key, "")
        if key:
            return cls(api_key=key)
        return None

    # Автоопределение по ключу
    if api_key:
        if api_key.startswith("sk-ant-"):
            return AnthropicProvider(api_key=api_key)
        elif api_key.startswith("sk-") or api_key.startswith("sk-proj-"):
            return OpenAIProvider(api_key=api_key)
        elif api_key.startswith("AIza"):
            return GeminiProvider(api_key=api_key)
        elif api_key.startswith("gsk_"):
            return GroqProvider(api_key=api_key)

    # Автоопределение по env
    for env_key, cls in [
        ("ANTHROPIC_API_KEY", AnthropicProvider),
        ("OPENAI_API_KEY", OpenAIProvider),
        ("GEMINI_API_KEY", GeminiProvider),
        ("GROQ_API_KEY", GroqProvider),
    ]:
        key = os.environ.get(env_key)
        if key:
            return cls(api_key=key)

    return None


def list_providers() -> list[dict]:
    """Список доступных провайдеров и их статус."""
    result = []
    for name, cls in PROVIDERS.items():
        env_key = cls.env_key
        available = bool(os.environ.get(env_key))
        result.append({
            "name": name,
            "display": cls.name,
            "env": env_key,
            "available": available,
        })
    return result


# --- Генерация ---

def generate_with_ai(
    table_name: str,
    columns: list[dict],
    row_count: int,
    ai_provider: AIProvider | None = None,
    api_key: str | None = None,
    context: str = "",
) -> list[dict] | None:
    """Генерировать данные для таблицы через AI.

    Автоматически определяет провайдера или использует переданный.
    Лимит 50 строк за раз (стоимость API).
    """
    provider = ai_provider or detect_provider(api_key)
    if not provider:
        return None

    row_count = min(row_count, 50)

    col_desc = ", ".join(
        f"{c['name']} ({c['type']}{'?' if c.get('nullable') else ''})"
        for c in columns
    )

    prompt = f"""Generate {row_count} realistic rows for the "{table_name}" table.
Columns: {col_desc}
{f"Context: {context}" if context else ""}

Requirements:
- Data must be realistic and internally consistent
- If column is a name in an organization table, use company names
- If column is a status, use realistic statuses (active, pending, etc.)
- Dates should be recent ISO format (within last 2 years)
- Respect nullable columns (occasionally set to null)
- Numbers should be realistic for context (price: 10-999, age: 18-80, etc.)

Return a JSON array of objects. Each object has column names as keys.
Return ONLY valid JSON, no markdown, no explanation."""

    try:
        text = provider.generate(prompt)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        return None


def build_schema_description(tables: dict) -> str:
    """Построить текстовое описание схемы для AI."""
    lines = []
    for table_name, table in tables.items():
        cols = []
        for col in table.columns:
            parts = [f"{col.name} {col.data_type}"]
            if col.is_primary:
                parts.append("PK")
            if col.fk_table:
                parts.append(f"FK->{col.fk_table}.{col.fk_column}")
            if not col.nullable:
                parts.append("NOT NULL")
            if col.is_unique:
                parts.append("UNIQUE")
            if col.enum_values:
                parts.append(f"ENUM({', '.join(col.enum_values[:5])})")
            cols.append(" ".join(parts))

        lines.append(f"TABLE {table_name}:")
        for c in cols:
            lines.append(f"  - {c}")
        lines.append("")

    return "\n".join(lines)
