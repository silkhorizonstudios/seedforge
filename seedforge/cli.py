"""Command-line interface."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from typing import Optional
from pathlib import Path

from seedforge.config import Config, DEFAULT_CONFIG_FILE
from seedforge.introspector import create_introspector
from seedforge.graph import DependencyGraph
from seedforge.generators import DataGenerator
from seedforge.inserter import BatchInserter

app = typer.Typer(
    name="seedforge",
    help="One command to fill your database with realistic test data.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def connect(
    db_url: str = typer.Argument(..., help="PostgreSQL connection string (postgresql://user:pass@host:port/dbname)"),
    save: bool = typer.Option(True, help="Save connection to .seedforge.yaml"),
):
    """Connect to a PostgreSQL database and save the connection."""
    console.print(f"\n[bold blue]Connecting to database...[/bold blue]")

    try:
        introspector = create_introspector(db_url)
        info = introspector.get_db_info()
        introspector.close()

        console.print(f"[bold green]Connected![/bold green] {info['database']} @ {info['host']}")
        console.print(f"  Tables: {info['table_count']}")
        console.print(f"  PostgreSQL: {info['version']}")

        if save:
            config = Config.load()
            config.db_url = db_url
            config.save()
            console.print(f"\n[dim]Saved to {DEFAULT_CONFIG_FILE}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Connection failed:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def inspect(
    db_url: Optional[str] = typer.Argument(None, help="Database connection string"),
    schema: str = typer.Option("", help="Database schema (default: auto-detect)"),
):
    """Inspect database schema: tables, columns, foreign keys."""
    db_url = _resolve_db_url(db_url)

    introspector = create_introspector(db_url)
    tables = introspector.get_tables(schema)
    introspector.close()

    if not tables:
        console.print("[yellow]No tables found.[/yellow]")
        raise typer.Exit(0)

    # Dependency graph + insertion order
    graph = DependencyGraph(tables)
    order = graph.topological_sort()

    console.print(f"\n[bold]Found {len(tables)} tables[/bold] (insertion order):\n")

    for i, table_name in enumerate(order, 1):
        table = tables[table_name]
        t = Table(title=f"{i}. {table_name}", title_style="bold cyan", show_lines=False)
        t.add_column("Column", style="white")
        t.add_column("Type", style="green")
        t.add_column("Nullable", style="yellow", width=8)
        t.add_column("FK → ", style="magenta")

        for col in table.columns:
            fk_str = f"{col.fk_table}.{col.fk_column}" if col.fk_table else ""
            nullable = "YES" if col.nullable else "NO"
            t.add_row(col.name, col.data_type, nullable, fk_str)

        console.print(t)
        console.print()

    # Stats
    total_cols = sum(len(t.columns) for t in tables.values())
    total_fks = sum(1 for t in tables.values() for c in t.columns if c.fk_table)
    console.print(f"[dim]Total: {len(tables)} tables, {total_cols} columns, {total_fks} foreign keys[/dim]\n")


@app.command()
def generate(
    db_url: Optional[str] = typer.Argument(None, help="Database connection string"),
    rows: int = typer.Option(100, "--rows", "-r", help="Rows per table"),
    schema: str = typer.Option("", help="Database schema (default: auto-detect)"),
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed for deterministic generation"),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export to file (sql/json) instead of inserting"),
    tables: Optional[str] = typer.Option(None, "--tables", "-t", help="Comma-separated list of tables to fill"),
    clean: bool = typer.Option(False, "--clean", help="TRUNCATE tables before inserting (CASCADE)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated without inserting"),
):
    """Generate realistic test data and insert into the database."""
    db_url = _resolve_db_url(db_url)

    with console.status("[bold blue]Reading schema...[/bold blue]"):
        introspector = create_introspector(db_url)
        all_tables = introspector.get_tables(schema)

    if not all_tables:
        console.print("[yellow]No tables found.[/yellow]")
        introspector.close()
        raise typer.Exit(0)

    # Filter tables
    if tables:
        table_list = [t.strip() for t in tables.split(",")]
        filtered = {k: v for k, v in all_tables.items() if k in table_list}
        if not filtered:
            console.print(f"[red]Tables not found: {tables}[/red]")
            introspector.close()
            raise typer.Exit(1)
        # Include FK parent tables
        for tbl in list(filtered.values()):
            for col in tbl.columns:
                if col.fk_table and col.fk_table in all_tables and col.fk_table not in filtered:
                    filtered[col.fk_table] = all_tables[col.fk_table]
        all_tables = filtered

    # Insertion order
    graph = DependencyGraph(all_tables)
    order = graph.topological_sort()

    console.print(f"\n[bold]Generating {rows} rows for {len(order)} tables[/bold]")
    if seed is not None:
        console.print(f"[dim]Seed: {seed}[/dim]")
    console.print()

    # Generate data
    generator = DataGenerator(seed=seed)
    generated_data = {}

    if export or dry_run:
        # Generate all data first, then export/preview
        for table_name in order:
            table = all_tables[table_name]
            with console.status(f"[blue]Generating {table_name}...[/blue]"):
                data = generator.generate_table(table, rows, generated_data)
                generated_data[table_name] = data
            console.print(f"  [green]✓[/green] {table_name}: {len(data)} rows")

        if export:
            _export_data(export, generated_data, all_tables, order)
        else:
            console.print(f"\n[yellow]Dry run — no data inserted.[/yellow]")
            _show_preview(generated_data, order)
    else:
        # Generate + insert per table so FK references use real DB IDs
        engine = introspector.get_db_info().get("engine", "PostgreSQL")
        inserter = BatchInserter(introspector.connection, engine=engine)
        if clean:
            with console.status("[yellow]Cleaning tables...[/yellow]"):
                inserter.truncate_tables(order)
            console.print("[yellow]Tables truncated.[/yellow]\n")

        total_inserted = 0
        try:
            for table_name in order:
                table = all_tables[table_name]
                data = generator.generate_table(table, rows, generated_data)
                generated_data[table_name] = data

                if data:
                    inserter.insert_table(table_name, data, all_tables)
                    # Read back real PKs for FK resolution in child tables
                    pk_cols = [c for c in table.columns if c.is_primary]
                    if pk_cols and not inserter._is_sqlite:
                        pk_name = pk_cols[0].name
                        q = inserter._q
                        cur = introspector.connection.cursor()
                        cur.execute(f'SELECT {q(pk_name)} FROM {q(table_name)}')
                        real_ids = [row[0] for row in cur.fetchall()]
                        cur.close()
                        if real_ids:
                            generated_data[table_name] = [{pk_name: rid} for rid in real_ids]

                    total_inserted += len(data)
                console.print(f"  [green]✓[/green] {table_name}: {len(data)} rows")

            introspector.connection.commit()
            console.print(f"\n[bold green]Done![/bold green] Inserted {total_inserted} rows into {len(order)} tables.\n")
        except Exception as e:
            introspector.connection.rollback()
            console.print(f"\n[bold red]Insert failed:[/bold red] {e}")
            console.print("[dim]Transaction rolled back, no data was written.[/dim]")
            raise typer.Exit(1)

    introspector.close()


@app.command()
def ai_generate(
    db_url: Optional[str] = typer.Argument(None, help="Database connection string"),
    rows: int = typer.Option(20, "--rows", "-r", help="Rows per table (max 50 for AI)"),
    schema: str = typer.Option("public", help="Database schema"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API key (auto-detects provider by prefix)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="AI provider: anthropic, openai, gemini, groq"),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export to file (sql/json)"),
):
    """Generate data using AI for maximum realism.

    Supports: Anthropic, OpenAI, Gemini, Groq.
    Auto-detects provider by API key prefix or env variable.
    """
    from seedforge.ai import generate_with_ai, detect_provider, list_providers

    ai = detect_provider(api_key, provider)
    if not ai:
        console.print("[red]No AI provider found.[/red]\n")
        console.print("Set one of these environment variables:")
        for p in list_providers():
            status = "[green]✓[/green]" if p["available"] else "[dim]–[/dim]"
            console.print(f"  {status} {p['env']:25s} {p['display']}")
        console.print(f"\nOr pass --api-key directly.")
        raise typer.Exit(1)

    console.print(f"[dim]Provider: {ai.name}[/dim]")

    db_url = _resolve_db_url(db_url)
    rows = min(rows, 50)

    with console.status("[bold blue]Reading schema...[/bold blue]"):
        introspector = create_introspector(db_url)
        all_tables = introspector.get_tables(schema)

    if not all_tables:
        console.print("[yellow]No tables found.[/yellow]")
        introspector.close()
        raise typer.Exit(0)

    from seedforge.graph import DependencyGraph
    graph = DependencyGraph(all_tables)
    order = graph.topological_sort()

    console.print(f"\n[bold]AI generating {rows} rows for {len(order)} tables[/bold]\n")

    generated_data = {}
    for table_name in order:
        table = all_tables[table_name]
        columns = [
            {"name": c.name, "type": c.data_type, "nullable": c.nullable}
            for c in table.columns
            if not (c.is_primary and c.is_serial)
        ]

        with console.status(f"[blue]AI generating {table_name}...[/blue]"):
            data = generate_with_ai(table_name, columns, rows, ai_provider=ai)

        if data:
            generated_data[table_name] = data
            console.print(f"  [green]✓[/green] {table_name}: {len(data)} rows (AI)")
        else:
            console.print(f"  [yellow]⚠[/yellow] {table_name}: AI failed, skipping")

    if export:
        _export_data(export, generated_data, all_tables, order)
    else:
        console.print(f"\n[bold green]Done![/bold green] Generated {sum(len(d) for d in generated_data.values())} rows.")
        _show_preview(generated_data, order)

    introspector.close()


@app.command()
def version():
    """Show SeedForge version."""
    from seedforge import __version__
    console.print(f"SeedForge v{__version__}")


def _resolve_db_url(db_url: Optional[str]) -> str:
    """Get DB URL from argument or config."""
    if db_url:
        return db_url
    config = Config.load()
    if config.db_url:
        return config.db_url
    console.print("[red]No database URL. Run 'seedforge connect <url>' first or pass it as argument.[/red]")
    raise typer.Exit(1)


def _export_data(format: str, data: dict, tables: dict, order: list):
    """Export data to file."""
    if format == "sql":
        from seedforge.inserter import BatchInserter
        sql = BatchInserter.generate_sql(data, tables, order)
        output_file = "seedforge_export.sql"
        Path(output_file).write_text(sql)
        console.print(f"\n[green]Exported to {output_file}[/green]")
    elif format == "json":
        import json
        output_file = "seedforge_export.json"
        # Convert to JSON-serializable format
        serializable = {}
        for table_name in order:
            serializable[table_name] = [
                {k: _json_safe(v) for k, v in row.items()}
                for row in data[table_name]
            ]
        Path(output_file).write_text(json.dumps(serializable, indent=2, ensure_ascii=False))
        console.print(f"\n[green]Exported to {output_file}[/green]")
    else:
        console.print(f"[red]Unknown format: {format}. Use 'sql' or 'json'.[/red]")


def _json_safe(value):
    """Convert value to JSON-safe type."""
    import datetime
    import decimal
    import uuid
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _show_preview(data: dict, order: list):
    """Show data preview."""
    for table_name in order:
        rows = data[table_name]
        if not rows:
            continue
        t = Table(title=table_name, title_style="bold cyan")
        cols = list(rows[0].keys())
        for col in cols:
            t.add_column(col)
        for row in rows[:5]:
            t.add_row(*[str(row.get(c, ""))[:40] for c in cols])
        if len(rows) > 5:
            t.add_row(*[f"... ({len(rows)} total)" if i == 0 else "..." for i, c in enumerate(cols)])
        console.print(t)
        console.print()


if __name__ == "__main__":
    app()
