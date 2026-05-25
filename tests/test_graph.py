"""Тесты для графа зависимостей и topological sort."""

from seedforge.introspector import TableInfo, Column
from seedforge.graph import DependencyGraph


def _make_tables(spec: dict[str, list[tuple[str, str | None]]]) -> dict[str, TableInfo]:
    """Хелпер: создать таблицы из спецификации.

    spec = {"users": [("id", None)], "orders": [("id", None), ("user_id", "users.id")]}
    """
    tables = {}
    for table_name, columns in spec.items():
        cols = []
        for col_name, fk in columns:
            fk_table = fk_column = None
            if fk:
                fk_table, fk_column = fk.split(".")
            cols.append(Column(name=col_name, data_type="integer", fk_table=fk_table, fk_column=fk_column))
        tables[table_name] = TableInfo(name=table_name, columns=cols)
    return tables


class TestTopologicalSort:
    def test_no_dependencies(self):
        tables = _make_tables({
            "users": [("id", None)],
            "products": [("id", None)],
        })
        graph = DependencyGraph(tables)
        order = graph.topological_sort()
        assert set(order) == {"users", "products"}

    def test_simple_dependency(self):
        tables = _make_tables({
            "users": [("id", None)],
            "orders": [("id", None), ("user_id", "users.id")],
        })
        graph = DependencyGraph(tables)
        order = graph.topological_sort()
        assert order.index("users") < order.index("orders")

    def test_chain_dependency(self):
        tables = _make_tables({
            "users": [("id", None)],
            "orders": [("id", None), ("user_id", "users.id")],
            "order_items": [("id", None), ("order_id", "orders.id")],
        })
        graph = DependencyGraph(tables)
        order = graph.topological_sort()
        assert order.index("users") < order.index("orders")
        assert order.index("orders") < order.index("order_items")

    def test_multiple_parents(self):
        tables = _make_tables({
            "users": [("id", None)],
            "products": [("id", None)],
            "orders": [("id", None), ("user_id", "users.id"), ("product_id", "products.id")],
        })
        graph = DependencyGraph(tables)
        order = graph.topological_sort()
        assert order.index("users") < order.index("orders")
        assert order.index("products") < order.index("orders")

    def test_self_reference_ignored(self):
        tables = _make_tables({
            "categories": [("id", None), ("parent_id", "categories.id")],
        })
        graph = DependencyGraph(tables)
        order = graph.topological_sort()
        assert order == ["categories"]

    def test_all_tables_included(self):
        tables = _make_tables({
            "a": [("id", None)],
            "b": [("id", None), ("a_id", "a.id")],
            "c": [("id", None), ("b_id", "b.id")],
            "d": [("id", None)],
        })
        graph = DependencyGraph(tables)
        order = graph.topological_sort()
        assert len(order) == 4
        assert set(order) == {"a", "b", "c", "d"}


class TestGetParents:
    def test_no_parents(self):
        tables = _make_tables({"users": [("id", None)]})
        graph = DependencyGraph(tables)
        assert graph.get_parents("users") == set()

    def test_has_parents(self):
        tables = _make_tables({
            "users": [("id", None)],
            "orders": [("id", None), ("user_id", "users.id")],
        })
        graph = DependencyGraph(tables)
        assert graph.get_parents("orders") == {"users"}
