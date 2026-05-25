"""FK dependency graph and insertion order resolution."""

from collections import defaultdict
from seedforge.introspector import TableInfo


class DependencyGraph:
    def __init__(self, tables: dict[str, TableInfo]):
        self.tables = tables
        self.edges: dict[str, set[str]] = defaultdict(set)  # child -> {parents}
        self._build()

    def _build(self):
        """Build dependency graph from FK relationships."""
        for table_name, table in self.tables.items():
            for col in table.columns:
                if col.fk_table and col.fk_table in self.tables and col.fk_table != table_name:
                    # table depends on fk_table
                    self.edges[table_name].add(col.fk_table)

    def topological_sort(self) -> list[str]:
        """Returns insertion order (parents first). Uses Kahn's algorithm."""
        # Count in-degrees
        in_degree: dict[str, int] = {name: 0 for name in self.tables}
        for table_name, parents in self.edges.items():
            in_degree[table_name] = len(parents)

        # Start with tables that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        queue.sort()  # deterministic order

        result = []
        visited = set()

        while queue:
            current = queue.pop(0)
            result.append(current)
            visited.add(current)

            # Decrease in-degree for dependent tables
            for table_name, parents in self.edges.items():
                if current in parents and table_name not in visited:
                    in_degree[table_name] -= 1
                    if in_degree[table_name] <= 0 and table_name not in visited:
                        queue.append(table_name)
                        queue.sort()

        # Handle cycles — append remaining tables
        remaining = [name for name in self.tables if name not in visited]
        remaining.sort()
        result.extend(remaining)

        return result

    def get_parents(self, table_name: str) -> set[str]:
        """Get parent tables that this table depends on."""
        return self.edges.get(table_name, set())
