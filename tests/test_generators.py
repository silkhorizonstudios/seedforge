"""Тесты для генераторов данных."""

import uuid
import datetime
from decimal import Decimal

from seedforge.introspector import TableInfo, Column
from seedforge.generators import DataGenerator


def _make_table(name: str, columns: list[Column]) -> TableInfo:
    return TableInfo(name=name, columns=columns)


class TestBasicGeneration:
    def test_generates_correct_row_count(self):
        table = _make_table("users", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="email", data_type="text", is_unique=True),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 10, {})
        assert len(rows) == 10

    def test_serial_pk_auto_generated(self):
        table = _make_table("users", [
            Column(name="id", data_type="integer", is_primary=True, is_serial=True),
            Column(name="name", data_type="text"),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 5, {})
        assert len(rows) == 5
        assert rows[0]["id"] == 1
        assert rows[4]["id"] == 5

    def test_uuid_pk_generated(self):
        table = _make_table("users", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="name", data_type="text"),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 3, {})
        for row in rows:
            assert "id" in row
            uuid.UUID(row["id"])  # должен быть валидный UUID

    def test_deterministic_with_seed(self):
        """Один и тот же seed в одном процессе даёт одинаковые данные."""
        table = _make_table("items", [
            Column(name="id", data_type="integer", is_primary=True, is_serial=True),
            Column(name="title", data_type="text"),
        ])
        gen1 = DataGenerator(seed=42)
        rows1 = gen1.generate_table(table, 5, {})
        gen2 = DataGenerator(seed=42)
        rows2 = gen2.generate_table(table, 5, {})
        assert rows1 == rows2


class TestForeignKeys:
    def test_fk_resolved(self):
        parent = _make_table("users", [
            Column(name="id", data_type="uuid", is_primary=True),
        ])
        child = _make_table("orders", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="user_id", data_type="uuid", fk_table="users", fk_column="id"),
        ])
        gen = DataGenerator(seed=42)
        parent_rows = gen.generate_table(parent, 3, {})
        parent_ids = {r["id"] for r in parent_rows}

        child_rows = gen.generate_table(child, 5, {"users": parent_rows})
        for row in child_rows:
            assert row["user_id"] in parent_ids

    def test_nullable_fk_without_parent(self):
        child = _make_table("orders", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="user_id", data_type="uuid", nullable=True, fk_table="users", fk_column="id"),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(child, 3, {})
        assert len(rows) == 3
        for row in rows:
            assert row["user_id"] is None


class TestEnumValues:
    def test_enum_used(self):
        table = _make_table("orders", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="status", data_type="order_status", enum_values=["pending", "paid", "cancelled"]),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 20, {})
        for row in rows:
            assert row["status"] in ["pending", "paid", "cancelled"]


class TestHeuristicTypes:
    def test_email_looks_like_email(self):
        table = _make_table("users", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="email", data_type="text"),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 5, {})
        for row in rows:
            if row["email"] is not None:  # 5% шанс NULL для nullable
                assert "@" in row["email"]

    def test_price_is_decimal(self):
        table = _make_table("products", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="price", data_type="numeric"),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 5, {})
        for row in rows:
            assert isinstance(row["price"], (Decimal, type(None)))

    def test_boolean_fields(self):
        table = _make_table("users", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="is_active", data_type="boolean"),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 50, {})
        values = [r["is_active"] for r in rows if r["is_active"] is not None]
        assert all(isinstance(v, bool) for v in values)
        # is_active should be biased towards True
        true_count = sum(1 for v in values if v is True)
        assert true_count > len(values) * 0.5


class TestUniqueConstraint:
    def test_unique_values(self):
        table = _make_table("users", [
            Column(name="id", data_type="uuid", is_primary=True),
            Column(name="email", data_type="text", is_unique=True),
        ])
        gen = DataGenerator(seed=42)
        rows = gen.generate_table(table, 50, {})
        emails = [r["email"] for r in rows]
        assert len(emails) == len(set(emails))
