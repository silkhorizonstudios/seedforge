"""Чтение схемы PostgreSQL: таблицы, колонки, типы, FK, constraints."""

import psycopg2
from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool = True
    is_primary: bool = False
    has_default: bool = False
    is_serial: bool = False  # serial / identity / nextval
    max_length: int | None = None
    # FK
    fk_table: str | None = None
    fk_column: str | None = None
    # Constraints
    is_unique: bool = False
    check_constraint: str | None = None
    enum_values: list[str] | None = None


@dataclass
class TableInfo:
    name: str
    columns: list[Column] = field(default_factory=list)


class Introspector:
    def __init__(self, db_url: str):
        self.connection = psycopg2.connect(db_url)
        self.connection.autocommit = True

    def close(self):
        self.connection.close()

    def get_db_info(self) -> dict:
        """Общая информация о БД."""
        cur = self.connection.cursor()
        cur.execute("SELECT current_database(), inet_server_addr(), version()")
        db, host, version = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
        count = cur.fetchone()[0]
        cur.close()
        return {
            "database": db,
            "host": str(host) if host else "localhost",
            "version": version.split(",")[0] if version else "unknown",
            "table_count": count,
        }

    def get_tables(self, schema: str = "public") -> dict[str, TableInfo]:
        """Получить все таблицы со всеми метаданными."""
        tables: dict[str, TableInfo] = {}
        cur = self.connection.cursor()

        # 1. Таблицы и колонки
        cur.execute("""
            SELECT
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.udt_name
            FROM information_schema.columns c
            JOIN information_schema.tables t
                ON c.table_name = t.table_name AND c.table_schema = t.table_schema
            WHERE c.table_schema = %s
                AND t.table_type = 'BASE TABLE'
            ORDER BY c.table_name, c.ordinal_position
        """, (schema,))

        for row in cur.fetchall():
            table_name, col_name, data_type, nullable, default, max_len, udt_name = row
            if table_name not in tables:
                tables[table_name] = TableInfo(name=table_name)

            is_serial = bool(default and ("nextval" in str(default) or "identity" in str(default).lower()))

            # Используем udt_name для USER-DEFINED типов (ENUM)
            if data_type == "USER-DEFINED":
                data_type = udt_name

            col = Column(
                name=col_name,
                data_type=data_type,
                nullable=nullable == "YES",
                has_default=default is not None,
                is_serial=is_serial,
                max_length=max_len,
            )
            tables[table_name].columns.append(col)

        # 2. Primary keys
        cur.execute("""
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = %s
        """, (schema,))

        for table_name, col_name in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.is_primary = True

        # 3. Foreign keys
        cur.execute("""
            SELECT
                kcu.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
        """, (schema,))

        for table_name, col_name, fk_table, fk_column in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.fk_table = fk_table
                        col.fk_column = fk_column

        # 4. Unique constraints
        cur.execute("""
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_schema = %s
        """, (schema,))

        for table_name, col_name in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.is_unique = True

        # 5. ENUM values
        cur.execute("""
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = %s
            ORDER BY t.typname, e.enumsortorder
        """, (schema,))

        enums: dict[str, list[str]] = {}
        for type_name, label in cur.fetchall():
            enums.setdefault(type_name, []).append(label)

        # Привязываем enum values к колонкам
        for table in tables.values():
            for col in table.columns:
                if col.data_type in enums:
                    col.enum_values = enums[col.data_type]

        cur.close()
        return tables
