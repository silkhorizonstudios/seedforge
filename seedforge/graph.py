"""Граф зависимостей таблиц + topological sort для определения порядка вставки."""

from collections import defaultdict
from seedforge.introspector import TableInfo


class DependencyGraph:
    def __init__(self, tables: dict[str, TableInfo]):
        self.tables = tables
        self.edges: dict[str, set[str]] = defaultdict(set)  # child -> {parents}
        self._build()

    def _build(self):
        """Построить граф зависимостей из FK."""
        for table_name, table in self.tables.items():
            for col in table.columns:
                if col.fk_table and col.fk_table in self.tables and col.fk_table != table_name:
                    # table зависит от fk_table (fk_table должна быть заполнена первой)
                    self.edges[table_name].add(col.fk_table)

    def topological_sort(self) -> list[str]:
        """Topological sort — возвращает порядок вставки (родители первые).

        Использует алгоритм Кана (BFS) для обработки циклов.
        """
        # Подсчёт входящих рёбер
        in_degree: dict[str, int] = {name: 0 for name in self.tables}
        for table_name, parents in self.edges.items():
            in_degree[table_name] = len(parents)

        # Таблицы без зависимостей — начальная очередь
        queue = [name for name, degree in in_degree.items() if degree == 0]
        queue.sort()  # детерминированный порядок

        result = []
        visited = set()

        while queue:
            current = queue.pop(0)
            result.append(current)
            visited.add(current)

            # Уменьшаем in_degree для зависимых таблиц
            for table_name, parents in self.edges.items():
                if current in parents and table_name not in visited:
                    in_degree[table_name] -= 1
                    if in_degree[table_name] <= 0 and table_name not in visited:
                        queue.append(table_name)
                        queue.sort()

        # Циклические зависимости — добавляем оставшиеся
        remaining = [name for name in self.tables if name not in visited]
        remaining.sort()
        result.extend(remaining)

        return result

    def get_parents(self, table_name: str) -> set[str]:
        """Получить родительские таблицы (от которых зависит)."""
        return self.edges.get(table_name, set())
