"""Генераторы данных — маппинг колонок на Faker + кастомные генераторы."""

import random
import uuid
import json
import hashlib
import datetime
from decimal import Decimal
from faker import Faker

from seedforge.introspector import TableInfo, Column
from seedforge.heuristics import match_generator


class DataGenerator:
    def __init__(self, seed: int | None = None, locale: str = "en_US"):
        self.faker = Faker(locale)
        self.seed = seed
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)
        # Трекинг уникальных значений
        self._unique_tracker: dict[str, set] = {}

    def generate_table(
        self,
        table: TableInfo,
        row_count: int,
        generated_data: dict[str, list[dict]],
    ) -> list[dict]:
        """Генерация данных для одной таблицы."""
        rows = []
        for i in range(row_count):
            row = self._generate_row(table, i, generated_data)
            if row:
                rows.append(row)
        return rows

    def _generate_row(
        self,
        table: TableInfo,
        row_index: int,
        generated_data: dict[str, list[dict]],
    ) -> dict | None:
        row = {}
        for col in table.columns:
            # Пропускаем serial/identity PK — БД сама генерирует
            if col.is_primary and col.is_serial:
                continue

            # FK — берём реальный ID из уже сгенерированных данных
            if col.fk_table and col.fk_column:
                value = self._resolve_fk(col, generated_data)
                if value is None and not col.nullable:
                    return None  # не можем создать строку без обязательного FK
                row[col.name] = value
                continue

            # Колонки с ENUM
            if col.enum_values:
                row[col.name] = random.choice(col.enum_values)
                continue

            # Генерация значения
            value = self._generate_value(col, table.name, row_index)

            # Уникальность
            if col.is_unique or (col.is_primary and not col.is_serial):
                value = self._ensure_unique(table.name, col.name, col, row_index)

            row[col.name] = value

        return row

    def _resolve_fk(self, col: Column, generated_data: dict[str, list[dict]]) -> object:
        """Получить значение FK из уже сгенерированных данных родительской таблицы."""
        parent_data = generated_data.get(col.fk_table, [])
        if not parent_data:
            return None

        parent_row = random.choice(parent_data)
        return parent_row.get(col.fk_column)

    def _generate_value(self, col: Column, table_name: str, row_index: int) -> object:
        """Генерация значения для колонки."""
        # Nullable — 5% шанс NULL
        if col.nullable and random.random() < 0.05:
            return None

        generator_name = match_generator(col.name, col.data_type)
        return self._call_generator(generator_name, col, row_index)

    def _call_generator(self, name: str, col: Column, row_index: int) -> object:
        """Вызвать генератор по имени."""
        # Стандартные Faker-методы
        if hasattr(self.faker, name):
            value = getattr(self.faker, name)()
            # Обрезаем строки под max_length
            if isinstance(value, str) and col.max_length and len(value) > col.max_length:
                value = value[:col.max_length]
            return value

        # Кастомные генераторы
        custom = {
            # Числа
            "_random_int": lambda: random.randint(1, 10000),
            "_random_bigint": lambda: random.randint(1, 1_000_000),
            "_random_smallint": lambda: random.randint(1, 1000),
            "_random_float": lambda: round(random.uniform(0.01, 10000.0), 2),
            "_random_decimal": lambda: Decimal(str(round(random.uniform(0.01, 10000.0), 2))),
            "_random_bool": lambda: random.choice([True, False]),
            "_random_char": lambda: random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),

            # Даты
            "_random_date": lambda: self.faker.date_between(start_date="-2y", end_date="today"),
            "_random_datetime": lambda: self.faker.date_time_between(start_date="-2y", end_date="now"),
            "_random_datetime_tz": lambda: self.faker.date_time_between(
                start_date="-2y", end_date="now", tzinfo=datetime.timezone.utc
            ),
            "_random_time": lambda: self.faker.time_object(),
            "_past_date": lambda: self.faker.date_of_birth(minimum_age=18, maximum_age=80),
            "_recent_datetime": lambda: self.faker.date_time_between(start_date="-1y", end_date="now"),
            "_recent_date": lambda: self.faker.date_between(start_date="-6m", end_date="today"),
            "_future_datetime": lambda: self.faker.date_time_between(start_date="now", end_date="+1y"),
            "_future_date": lambda: self.faker.date_between(start_date="today", end_date="+1y"),
            "_random_interval": lambda: f"{random.randint(1, 365)} days",

            # Специальные
            "_price": lambda: Decimal(str(round(random.uniform(1.0, 9999.99), 2))),
            "_image_url": lambda: f"https://picsum.photos/seed/{random.randint(1, 10000)}/400/300",
            "_true_biased": lambda: random.random() < 0.85,  # 85% True
            "_false_biased": lambda: random.random() < 0.1,   # 10% True
            "_password_hash": lambda: hashlib.sha256(self.faker.password().encode()).hexdigest(),
            "_token": lambda: uuid.uuid4().hex + uuid.uuid4().hex,
            "_random_json": lambda: json.dumps({"key": self.faker.word(), "value": self.faker.sentence()}),
            "_random_bytes": lambda: b"\\x00",
            "_empty_array": lambda: "{}",
        }

        if name in custom:
            return custom[name]()

        # Абсолютный fallback
        return self.faker.sentence()

    def _ensure_unique(self, table_name: str, col_name: str, col: Column, row_index: int) -> object:
        """Гарантировать уникальность значения."""
        key = f"{table_name}.{col_name}"
        if key not in self._unique_tracker:
            self._unique_tracker[key] = set()

        # Если PK не serial — генерируем последовательные ID
        if col.is_primary:
            data_type = col.data_type.lower()
            if data_type == "uuid":
                value = str(uuid.uuid4())
                self._unique_tracker[key].add(value)
                return value
            elif data_type in ("integer", "bigint", "smallint", "serial", "bigserial"):
                value = row_index + 1
                self._unique_tracker[key].add(value)
                return value

        # Для остальных уникальных колонок — пробуем до 100 раз
        generator_name = match_generator(col_name, col.data_type)
        for _ in range(100):
            value = self._call_generator(generator_name, col, row_index)
            if value not in self._unique_tracker[key]:
                self._unique_tracker[key].add(value)
                return value

        # Если не удалось — добавляем суффикс
        base_value = self._call_generator(generator_name, col, row_index)
        if isinstance(base_value, str):
            value = f"{base_value}_{row_index}"
            if col.max_length and len(value) > col.max_length:
                value = value[:col.max_length]
        else:
            value = row_index + 10000

        self._unique_tracker[key].add(value)
        return value
