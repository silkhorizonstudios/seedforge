"""Batch data insertion with multi-database support."""

import json
import datetime
import decimal
import uuid as uuid_mod

from seedforge.introspector import TableInfo


class BatchInserter:
    BATCH_SIZE = 500

    def __init__(self, connection, engine: str = "PostgreSQL"):
        self.connection = connection
        self.engine = engine.lower()
        self._is_mysql = self.engine in ("mysql", "mariadb")
        self._is_sqlite = self.engine == "sqlite"
        self._q = "`" if self._is_mysql else '"'

    def insert_all(
        self,
        data: dict[str, list[dict]],
        tables: dict[str, TableInfo],
        order: list[str],
    ):
        """Insert all data in topological order."""
        old_autocommit = getattr(self.connection, 'autocommit', None)
        if old_autocommit is not None:
            self.connection.autocommit = False

        try:
            cur = self.connection.cursor()
            q = self._q

            for table_name in order:
                rows = data.get(table_name, [])
                if not rows:
                    continue

                # For PostgreSQL: set serial sequences to start after our IDs
                if not self._is_sqlite and not self._is_mysql:
                    table = tables.get(table_name)
                    if table:
                        for col in table.columns:
                            if col.is_primary and col.is_serial:
                                max_id = max((r.get(col.name, 0) for r in rows), default=0)
                                if isinstance(max_id, int) and max_id > 0:
                                    cur.execute(
                                        f"SELECT setval(pg_get_serial_sequence('{table_name}', '{col.name}'), %s, true)",
                                        (max_id,)
                                    )

                columns = list(rows[0].keys())
                col_list = ", ".join(f'{q}{c}{q}' for c in columns)
                placeholders = ", ".join(["%s"] * len(columns))

                for i in range(0, len(rows), self.BATCH_SIZE):
                    batch = rows[i:i + self.BATCH_SIZE]
                    values = [
                        tuple(self._prep_value(row.get(c)) for c in columns)
                        for row in batch
                    ]

                    if self._is_sqlite:
                        ph = ", ".join(["?"] * len(columns))
                        sql = f'INSERT OR IGNORE INTO {q}{table_name}{q} ({col_list}) VALUES ({ph})'
                        cur.executemany(sql, values)
                    elif self._is_mysql:
                        sql = f'INSERT IGNORE INTO {q}{table_name}{q} ({col_list}) VALUES ({placeholders})'
                        cur.executemany(sql, values)
                    else:
                        from psycopg2.extras import execute_values
                        template = "(" + ", ".join(["%s"] * len(columns)) + ")"
                        sql = f'INSERT INTO {q}{table_name}{q} ({col_list}) VALUES %s ON CONFLICT DO NOTHING'
                        execute_values(cur, sql, values, template=template)

                # After insert, refresh data with actual PKs from DB for FK resolution
                table = tables.get(table_name)
                if table and not self._is_sqlite:
                    pk_cols = [c for c in table.columns if c.is_primary]
                    if pk_cols:
                        pk_name = pk_cols[0].name
                        cur.execute(f'SELECT {q}{pk_name}{q} FROM {q}{table_name}{q}')
                        real_ids = [row[0] for row in cur.fetchall()]
                        if real_ids:
                            data[table_name] = [{pk_name: rid} for rid in real_ids]

            self.connection.commit()
            cur.close()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            if old_autocommit is not None:
                self.connection.autocommit = old_autocommit

    def insert_table(self, table_name: str, rows: list[dict], tables: dict):
        """Insert rows for a single table."""
        if not rows:
            return
        q = self._q
        cur = self.connection.cursor()
        columns = list(rows[0].keys())
        col_list = ", ".join(f'{q}{c}{q}' for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))

        # Set serial sequence
        table = tables.get(table_name)
        if table and not self._is_sqlite and not self._is_mysql:
            for col in table.columns:
                if col.is_primary and col.is_serial:
                    max_id = max((r.get(col.name, 0) for r in rows), default=0)
                    if isinstance(max_id, int) and max_id > 0:
                        try:
                            cur.execute(
                                f"SELECT setval(pg_get_serial_sequence('{table_name}', '{col.name}'), %s, true)",
                                (max_id,)
                            )
                        except Exception:
                            pass

        for i in range(0, len(rows), self.BATCH_SIZE):
            batch = rows[i:i + self.BATCH_SIZE]
            values = [
                tuple(self._prep_value(row.get(c)) for c in columns)
                for row in batch
            ]
            if self._is_sqlite:
                ph = ", ".join(["?"] * len(columns))
                cur.executemany(f'INSERT OR IGNORE INTO {q}{table_name}{q} ({col_list}) VALUES ({ph})', values)
            elif self._is_mysql:
                cur.executemany(f'INSERT IGNORE INTO {q}{table_name}{q} ({col_list}) VALUES ({placeholders})', values)
            else:
                from psycopg2.extras import execute_values
                template = "(" + ", ".join(["%s"] * len(columns)) + ")"
                execute_values(cur, f'INSERT INTO {q}{table_name}{q} ({col_list}) VALUES %s ON CONFLICT DO NOTHING', values, template=template)

        cur.close()

    def truncate_tables(self, order: list[str]):
        """Truncate tables in reverse order (children first)."""
        q = self._q
        cur = self.connection.cursor()
        if self._is_sqlite:
            for table_name in reversed(order):
                cur.execute(f'DELETE FROM {q}{table_name}{q}')
        elif self._is_mysql:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table_name in reversed(order):
                cur.execute(f'TRUNCATE TABLE {q}{table_name}{q}')
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        else:
            for table_name in reversed(order):
                cur.execute(f'TRUNCATE TABLE {q}{table_name}{q} CASCADE')
        cur.close()

    @staticmethod
    def generate_sql(
        data: dict[str, list[dict]],
        tables: dict[str, TableInfo],
        order: list[str],
        engine: str = "PostgreSQL",
    ) -> str:
        """Generate SQL file with INSERT statements."""
        is_mysql = engine.lower() in ("mysql", "mariadb")
        q = "`" if is_mysql else '"'

        lines = ["-- Generated by SeedForge", "-- https://github.com/silkhorizonstudios/seedforge", ""]
        if is_mysql:
            lines.append("SET FOREIGN_KEY_CHECKS = 0;")
        lines.append("BEGIN;")
        lines.append("")

        for table_name in order:
            rows = data.get(table_name, [])
            if not rows:
                continue

            columns = list(rows[0].keys())
            col_list = ", ".join(f'{q}{c}{q}' for c in columns)

            lines.append(f"-- {table_name} ({len(rows)} rows)")

            for row in rows:
                values = ", ".join(
                    BatchInserter._sql_value(row.get(c)) for c in columns
                )
                lines.append(f'INSERT INTO {q}{table_name}{q} ({col_list}) VALUES ({values});')

            lines.append("")

        lines.append("COMMIT;")
        if is_mysql:
            lines.append("SET FOREIGN_KEY_CHECKS = 1;")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _prep_value(value):
        """Prepare value for the DB driver."""
        if value is None:
            return None
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, decimal.Decimal):
            return float(value)
        return value

    @staticmethod
    def _sql_value(value) -> str:
        """Convert value to SQL literal."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float, decimal.Decimal)):
            return str(value)
        if isinstance(value, (datetime.date, datetime.datetime)):
            return f"'{value.isoformat()}'"
        if isinstance(value, uuid_mod.UUID):
            return f"'{value}'"
        if isinstance(value, dict):
            escaped = json.dumps(value).replace("'", "''")
            return f"'{escaped}'"
        if isinstance(value, bytes):
            return f"'\\x{value.hex()}'"
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"
