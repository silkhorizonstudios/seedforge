"""Data generation engine."""

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
        self._unique_tracker: dict[str, set] = {}

    def generate_table(
        self,
        table: TableInfo,
        row_count: int,
        generated_data: dict[str, list[dict]],
    ) -> list[dict]:
        """Generate rows for a single table."""
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
            if col.is_primary and col.is_serial:
                # Generate explicit ID for FK references
                row[col.name] = row_index + 1
                continue

            if col.fk_table and col.fk_column:
                value = self._resolve_fk(col, generated_data)
                if value is None and not col.nullable:
                    return None
                row[col.name] = value
                continue

            if col.enum_values:
                row[col.name] = random.choice(col.enum_values)
                continue

            value = self._generate_value(col, table.name, row_index)

            if col.is_unique or (col.is_primary and not col.is_serial):
                value = self._ensure_unique(table.name, col.name, col, row_index)

            row[col.name] = value

        return row

    def _resolve_fk(self, col: Column, generated_data: dict[str, list[dict]]) -> object:
        """Resolve FK value from already-generated parent data."""
        parent_data = generated_data.get(col.fk_table, [])
        if not parent_data:
            return None
        parent_row = random.choice(parent_data)
        return parent_row.get(col.fk_column)

    def _generate_value(self, col: Column, table_name: str, row_index: int) -> object:
        """Generate a value for a column."""
        if col.nullable and random.random() < 0.05:
            return None

        # Force correct generator for structured types regardless of column name
        dtype = col.data_type.lower()
        if dtype in ("json", "jsonb"):
            return self._call_generator("_random_json", col, row_index)
        if "[]" in dtype or dtype == "array" or dtype.startswith("_"):
            return self._call_generator("_empty_array", col, row_index)

        generator_name = match_generator(col.name, col.data_type, table_name)
        value = self._call_generator(generator_name, col, row_index)

        # Cast booleans to int for integer columns
        int_types = ("integer", "bigint", "smallint", "int", "int2", "int4", "int8")
        if isinstance(value, bool) and col.data_type.lower() in int_types:
            value = 1 if value else 0

        return value

    def _call_generator(self, name: str, col: Column, row_index: int) -> object:
        """Call generator by name."""
        # Standard Faker methods
        if hasattr(self.faker, name):
            value = getattr(self.faker, name)()
            if isinstance(value, str) and col.max_length and len(value) > col.max_length:
                value = value[:col.max_length]
            return value

        # Custom generators
        custom = {
            # Numbers
            "_random_int": lambda: random.randint(1, 10000),
            "_random_bigint": lambda: random.randint(1, 1_000_000),
            "_random_smallint": lambda: random.randint(1, 1000),
            "_random_float": lambda: round(random.uniform(0.01, 10000.0), 2),
            "_random_decimal": lambda: Decimal(str(round(random.uniform(0.01, 999.99), 2))),
            "_random_bool": lambda: random.choice([True, False]),
            "_random_char": lambda: random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),

            # Dates
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

            # Special
            "_price": lambda: Decimal(str(round(random.uniform(1.0, 999.99), 2))),
            "_percentage": lambda: Decimal(str(round(random.uniform(0.0, 100.0), 1))),
            "_image_url": lambda: f"https://picsum.photos/seed/{random.randint(1, 10000)}/400/300",
            "_true_biased": lambda: random.random() < 0.85,
            "_false_biased": lambda: random.random() < 0.1,
            "_password_hash": lambda: hashlib.sha256(self.faker.password().encode()).hexdigest(),
            "_token": lambda: uuid.uuid4().hex + uuid.uuid4().hex,
            "_random_json": lambda: json.dumps({"key": self.faker.word(), "value": self.faker.sentence()}),
            "_random_bytes": lambda: b"\\x00",
            "_empty_array": lambda: "{}",

            # Context-aware
            "_context_name": lambda: self.faker.name(),
            "_short_title": lambda: self.faker.sentence(nb_words=random.randint(2, 5)).rstrip("."),
            "_product_name": lambda: f"{self.faker.word().title()} {random.choice(['Pro', 'Plus', 'Lite', 'Max', 'Ultra', 'Basic', 'Premium', 'Standard'])}",
            "_service_name": lambda: random.choice([
                "Consultation", "Diagnostics", "Maintenance", "Support",
                "Installation", "Training", "Audit", "Review",
                "Optimization", "Analysis", "Assessment", "Repair",
            ]),
            "_category_name": lambda: random.choice([
                "Electronics", "Clothing", "Health", "Education", "Finance",
                "Entertainment", "Food", "Travel", "Sports", "Technology",
                "Science", "Art", "Music", "Books", "Games", "Automotive",
            ]),
            "_department_name": lambda: random.choice([
                "Engineering", "Marketing", "Sales", "HR", "Finance",
                "Support", "Operations", "Legal", "Design", "Product",
            ]),
            "_team_name": lambda: f"Team {self.faker.word().title()}",
            "_project_name": lambda: f"Project {self.faker.word().title()}",
            "_event_name": lambda: f"{random.choice(['Annual', 'Monthly', 'Weekly', 'Q1', 'Q2', 'Q3', 'Q4'])} {random.choice(['Meeting', 'Review', 'Conference', 'Workshop', 'Summit', 'Webinar'])}",
            "_course_name": lambda: f"{random.choice(['Introduction to', 'Advanced', 'Fundamentals of', 'Practical'])} {self.faker.word().title()}",
            "_test_name": lambda: f"{random.choice(['Personality', 'Aptitude', 'Skills', 'Knowledge', 'Assessment'])} Test {random.randint(1, 100)}",
            "_room_name": lambda: f"Room {random.choice(['A', 'B', 'C', 'D'])}-{random.randint(100, 999)}",

            # Roles and statuses
            "_role": lambda: random.choice(["admin", "user", "moderator", "editor", "viewer", "member", "owner", "manager"]),
            "_status": lambda: random.choice(["active", "inactive", "pending", "completed", "cancelled", "draft", "approved", "rejected"]),
            "_type_field": lambda: random.choice(["standard", "premium", "basic", "custom", "default", "special"]),
            "_priority": lambda: random.choice(["low", "medium", "high", "critical", "urgent"]),
            "_plan": lambda: random.choice(["free", "starter", "pro", "business", "enterprise"]),
            "_gender": lambda: random.choice(["male", "female", "other"]),

            # Contextual numbers
            "_count": lambda: random.randint(0, 5000),
            "_rating": lambda: round(random.uniform(1.0, 5.0), 1),
            "_sort_order": lambda: row_index + 1,
            "_capacity": lambda: random.choice([5, 10, 25, 50, 100, 250, 500, 1000]),
            "_year": lambda: random.randint(1990, 2026),
            "_age": lambda: random.randint(18, 80),
            "_duration": lambda: random.randint(1, 480),
            "_dimension": lambda: random.randint(50, 4000),

            # Codes
            "_code": lambda: self.faker.bothify("??-####").upper(),
            "_social_id": lambda: str(random.randint(100000000, 999999999999)),
            "_id_array": lambda: json.dumps([str(uuid.uuid4()) for _ in range(random.randint(1, 5))]),
        }

        if name in custom:
            value = custom[name]()
            if isinstance(value, str) and col.max_length and len(value) > col.max_length:
                value = value[:col.max_length]
            return value

        value = self.faker.sentence()
        if isinstance(value, str) and col.max_length and len(value) > col.max_length:
            value = value[:col.max_length]
        return value

    def _ensure_unique(self, table_name: str, col_name: str, col: Column, row_index: int) -> object:
        """Ensure value uniqueness."""
        key = f"{table_name}.{col_name}"
        if key not in self._unique_tracker:
            self._unique_tracker[key] = set()

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

        generator_name = match_generator(col_name, col.data_type, table_name)
        for _ in range(100):
            value = self._call_generator(generator_name, col, row_index)
            if value not in self._unique_tracker[key]:
                self._unique_tracker[key].add(value)
                return value

        base_value = self._call_generator(generator_name, col, row_index)
        if isinstance(base_value, str):
            value = f"{base_value}_{row_index}"
            if col.max_length and len(value) > col.max_length:
                value = value[:col.max_length]
        else:
            value = row_index + 10000

        self._unique_tracker[key].add(value)
        return value
