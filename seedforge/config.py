"""Конфигурация SeedForge (.seedforge.yaml)."""

import yaml
from pathlib import Path
from dataclasses import dataclass, field

DEFAULT_CONFIG_FILE = ".seedforge.yaml"


@dataclass
class Config:
    db_url: str = ""
    default_rows: int = 100
    default_schema: str = "public"
    seed: int | None = None
    exclude_tables: list[str] = field(default_factory=list)
    # Кастомные генераторы для колонок
    # Формат: {"table.column": {"type": "faker_method", "args": {...}}}
    custom_generators: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str = DEFAULT_CONFIG_FILE) -> "Config":
        """Загрузить конфиг из файла."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return cls(
            db_url=data.get("db_url", ""),
            default_rows=data.get("default_rows", 100),
            default_schema=data.get("default_schema", "public"),
            seed=data.get("seed"),
            exclude_tables=data.get("exclude_tables", []),
            custom_generators=data.get("custom_generators", {}),
        )

    def save(self, path: str = DEFAULT_CONFIG_FILE):
        """Сохранить конфиг в файл."""
        data = {
            "db_url": self.db_url,
            "default_rows": self.default_rows,
            "default_schema": self.default_schema,
        }
        if self.seed is not None:
            data["seed"] = self.seed
        if self.exclude_tables:
            data["exclude_tables"] = self.exclude_tables
        if self.custom_generators:
            data["custom_generators"] = self.custom_generators

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
