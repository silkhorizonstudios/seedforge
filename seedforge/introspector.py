"""Database schema introspection for PostgreSQL, MySQL, and SQLite."""

from __future__ import annotations
from dataclasses import dataclass, field
from urllib.parse import urlparse

# System/migration tables to skip
SYSTEM_TABLES = {
    "_prisma_migrations",
    "django_migrations", "django_content_type", "django_admin_log",
    "django_session", "auth_permission", "auth_group",
    "auth_group_permissions", "auth_user_groups", "auth_user_user_permissions",
    "knex_migrations", "knex_migrations_lock",
    "typeorm_metadata", "migrations",
    "alembic_version",
    "__drizzle_migrations",
    "SequelizeMeta",
    "flyway_schema_history",
    "databasechangelog", "databasechangeloglock",
    "spatial_ref_sys",
}


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool = True
    is_primary: bool = False
    has_default: bool = False
    is_serial: bool = False
    max_length: int | None = None
    fk_table: str | None = None
    fk_column: str | None = None
    is_unique: bool = False
    check_constraint: str | None = None
    enum_values: list[str] | None = None


@dataclass
class TableInfo:
    name: str
    columns: list[Column] = field(default_factory=list)


def create_introspector(db_url: str) -> "Introspector":
    """Create the right introspector for the given URL."""
    parsed = urlparse(db_url)
    scheme = parsed.scheme.lower()

    if scheme in ("postgresql", "postgres", "psql", "postgresql+psycopg2", "pg"):
        return PostgresIntrospector(db_url)
    elif scheme in ("mysql", "mysql+pymysql", "mariadb"):
        return MySQLIntrospector(db_url)
    elif scheme in ("sqlite", "sqlite3"):
        return SQLiteIntrospector(db_url)
    else:
        raise ValueError(f"Unsupported database: {scheme}. Supported: postgresql/psql/pg, mysql/mariadb, sqlite")


class Introspector:
    """Base introspector class."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.connection = None

    def close(self):
        if self.connection:
            self.connection.close()

    def get_db_info(self) -> dict:
        raise NotImplementedError

    def get_tables(self, schema: str = "") -> dict[str, TableInfo]:
        raise NotImplementedError


class PostgresIntrospector(Introspector):
    def __init__(self, db_url: str):
        super().__init__(db_url)
        import psycopg2
        self.connection = psycopg2.connect(db_url)
        self.connection.autocommit = True

    def get_db_info(self) -> dict:
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
            "engine": "PostgreSQL",
        }

    def get_tables(self, schema: str = "public") -> dict[str, TableInfo]:
        if not schema:
            schema = "public"
        tables: dict[str, TableInfo] = {}
        cur = self.connection.cursor()

        # 1. Tables and columns
        cur.execute("""
            SELECT c.table_name, c.column_name, c.data_type, c.is_nullable,
                   c.column_default, c.character_maximum_length, c.udt_name
            FROM information_schema.columns c
            JOIN information_schema.tables t
                ON c.table_name = t.table_name AND c.table_schema = t.table_schema
            WHERE c.table_schema = %s AND t.table_type = 'BASE TABLE'
            ORDER BY c.table_name, c.ordinal_position
        """, (schema,))

        for row in cur.fetchall():
            table_name, col_name, data_type, nullable, default, max_len, udt_name = row
            if table_name in SYSTEM_TABLES:
                continue
            if table_name not in tables:
                tables[table_name] = TableInfo(name=table_name)

            is_serial = bool(default and ("nextval" in str(default) or "identity" in str(default).lower()))
            if data_type == "USER-DEFINED":
                data_type = udt_name

            col = Column(
                name=col_name, data_type=data_type,
                nullable=nullable == "YES", has_default=default is not None,
                is_serial=is_serial, max_length=max_len,
            )
            tables[table_name].columns.append(col)

        # 2. Primary keys
        cur.execute("""
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s
        """, (schema,))
        for table_name, col_name in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.is_primary = True

        # 3. Foreign keys
        cur.execute("""
            SELECT kcu.table_name, kcu.column_name,
                   ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
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
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = %s
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
        for table in tables.values():
            for col in table.columns:
                if col.data_type in enums:
                    col.enum_values = enums[col.data_type]

        cur.close()
        return tables


class MySQLIntrospector(Introspector):
    def __init__(self, db_url: str):
        super().__init__(db_url)
        import pymysql
        parsed = urlparse(db_url)
        self.db_name = parsed.path.lstrip("/")
        self.connection = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=self.db_name,
            charset="utf8mb4",
        )

    def get_db_info(self) -> dict:
        cur = self.connection.cursor()
        cur.execute("SELECT DATABASE(), @@hostname, VERSION()")
        db, host, version = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'",
            (self.db_name,)
        )
        count = cur.fetchone()[0]
        cur.close()
        return {
            "database": db,
            "host": host or "localhost",
            "version": f"MySQL {version}",
            "table_count": count,
            "engine": "MySQL",
        }

    def get_tables(self, schema: str = "") -> dict[str, TableInfo]:
        db = schema or self.db_name
        tables: dict[str, TableInfo] = {}
        cur = self.connection.cursor()

        # 1. Tables and columns
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable,
                   column_default, character_maximum_length, column_type, extra
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
        """, (db,))

        for row in cur.fetchall():
            table_name, col_name, data_type, nullable, default, max_len, col_type, extra = row
            if table_name in SYSTEM_TABLES:
                continue
            if table_name not in tables:
                tables[table_name] = TableInfo(name=table_name)

            is_serial = "auto_increment" in (extra or "").lower()

            # Parse MySQL ENUM from column_type
            enum_values = None
            if data_type == "enum" and col_type:
                import re
                matches = re.findall(r"'([^']*)'", col_type)
                if matches:
                    enum_values = matches

            col = Column(
                name=col_name, data_type=data_type,
                nullable=nullable == "YES", has_default=default is not None,
                is_serial=is_serial, max_length=max_len,
                enum_values=enum_values,
            )
            tables[table_name].columns.append(col)

        # 2. Primary keys
        cur.execute("""
            SELECT table_name, column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = %s AND constraint_name = 'PRIMARY'
        """, (db,))
        for table_name, col_name in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.is_primary = True

        # 3. Foreign keys
        cur.execute("""
            SELECT table_name, column_name, referenced_table_name, referenced_column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = %s
                AND referenced_table_name IS NOT NULL
        """, (db,))
        for table_name, col_name, fk_table, fk_column in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.fk_table = fk_table
                        col.fk_column = fk_column

        # 4. Unique constraints
        cur.execute("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = %s
        """, (db,))
        for table_name, col_name in cur.fetchall():
            if table_name in tables:
                for col in tables[table_name].columns:
                    if col.name == col_name:
                        col.is_unique = True

        cur.close()
        return tables


class SQLiteIntrospector(Introspector):
    def __init__(self, db_url: str):
        super().__init__(db_url)
        import sqlite3
        parsed = urlparse(db_url)
        self.db_path = parsed.path
        if self.db_path.startswith("///"):
            self.db_path = self.db_path[3:]
        elif self.db_path.startswith("//"):
            self.db_path = self.db_path[2:]
        self.connection = sqlite3.connect(self.db_path)

    def get_db_info(self) -> dict:
        import sqlite3
        cur = self.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        count = cur.fetchone()[0]
        cur.close()
        return {
            "database": self.db_path,
            "host": "local",
            "version": f"SQLite {sqlite3.sqlite_version}",
            "table_count": count,
            "engine": "SQLite",
        }

    def get_tables(self, schema: str = "") -> dict[str, TableInfo]:
        import re
        tables: dict[str, TableInfo] = {}
        cur = self.connection.cursor()

        # Get table list
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        table_names = [row[0] for row in cur.fetchall()]

        for table_name in table_names:
            if table_name in SYSTEM_TABLES:
                continue
            tables[table_name] = TableInfo(name=table_name)

            # Columns via PRAGMA
            cur.execute(f'PRAGMA table_info("{table_name}")')
            for row in cur.fetchall():
                cid, col_name, col_type, notnull, default, pk = row
                col_type_lower = (col_type or "text").lower()
                is_serial = pk == 1 and "integer" in col_type_lower

                col = Column(
                    name=col_name,
                    data_type=col_type or "text",
                    nullable=not notnull and pk != 1,
                    has_default=default is not None,
                    is_serial=is_serial,
                    is_primary=pk == 1,
                )
                len_match = re.search(r"\((\d+)\)", col_type or "")
                if len_match:
                    col.max_length = int(len_match.group(1))
                tables[table_name].columns.append(col)

            # FK via PRAGMA
            cur.execute(f'PRAGMA foreign_key_list("{table_name}")')
            for row in cur.fetchall():
                fk_table, col_from, col_to = row[2], row[3], row[4]
                for col in tables[table_name].columns:
                    if col.name == col_from:
                        col.fk_table = fk_table
                        col.fk_column = col_to

            # Unique indexes
            cur.execute(f'PRAGMA index_list("{table_name}")')
            for idx_row in cur.fetchall():
                idx_name, unique = idx_row[1], idx_row[2]
                if unique:
                    cur.execute(f'PRAGMA index_info("{idx_name}")')
                    for info_row in cur.fetchall():
                        for col in tables[table_name].columns:
                            if col.name == info_row[2]:
                                col.is_unique = True

        cur.close()
        return tables
