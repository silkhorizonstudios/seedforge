# SeedForge

[![PyPI version](https://img.shields.io/pypi/v/seedforge.svg)](https://pypi.org/project/seedforge/)
[![Python](https://img.shields.io/pypi/pyversions/seedforge.svg)](https://pypi.org/project/seedforge/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Database seeding tool. Connects to your DB, reads the schema, generates realistic data with valid foreign keys.

```bash
pip install seedforge
seedforge connect postgresql://user:pass@localhost/mydb
seedforge generate --rows 1000
```

## Why

I got tired of writing seed scripts by hand every time I start a new project. You know the drill — empty dashboards, nothing to test against, and if you copy prod data you're asking for GDPR trouble.

SeedForge reads your schema and figures out the rest. It knows that `orders.user_id` points to `users.id`, so it fills `users` first. It knows that a column called `email` should look like an email, not random gibberish.

## Install

```bash
pip install seedforge          # PostgreSQL + SQLite
pip install seedforge[mysql]   # + MySQL/MariaDB
pip install seedforge[ai]      # + AI providers
pip install seedforge[all]     # everything
```

## Usage

```bash
# save connection (writes .seedforge.yaml)
seedforge connect postgresql://user:pass@localhost:5432/mydb
seedforge connect mysql://user:pass@localhost:3306/mydb
seedforge connect sqlite:///path/to/db.sqlite

# see what's in the database
seedforge inspect

# generate and insert
seedforge generate --rows 100

# just preview, don't touch the DB
seedforge generate --rows 10 --dry-run

# export instead of inserting
seedforge generate --rows 1000 --export sql
seedforge generate --rows 1000 --export json

# same data every time
seedforge generate --rows 100 --seed 42

# specific tables only (pulls in FK parents automatically)
seedforge generate --tables orders,payments --rows 50

# wipe tables first
seedforge generate --rows 100 --clean
```

## AI mode

If you want smarter data (realistic product names, proper bios, etc.), you can plug in an API key. SeedForge auto-detects the provider:

```bash
seedforge ai-generate --api-key sk-ant-...   # Anthropic
seedforge ai-generate --api-key sk-...       # OpenAI
seedforge ai-generate --api-key AIza...      # Google Gemini
seedforge ai-generate --api-key gsk_...      # Groq
```

Or set an env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`) and just run `seedforge ai-generate`.

Only schema metadata goes to the API — table and column names, never your actual data.

## How it works

1. Connects to your database and reads `information_schema` (PostgreSQL/MySQL) or `PRAGMA` (SQLite)
2. Builds a dependency graph from foreign keys, topological sort gives the insertion order
3. For each column, picks a generator based on the name — `email` gets a realistic email, `price` gets a decimal, `created_at` gets a recent timestamp, and so on (80+ patterns)
4. Foreign key columns get real IDs from already-generated parent rows
5. Batch inserts everything in a single transaction

## What it recognizes

Some examples — there are 80+ patterns total:

| Column | Data |
|---|---|
| `email` | `john.smith@example.com` |
| `phone` | `+1-555-0123` |
| `first_name` / `last_name` | `John` / `Smith` |
| `price`, `amount` | `49.99` |
| `role` | `admin`, `user`, `moderator` |
| `status` | `active`, `pending`, `completed` |
| `created_at` | recent datetime |
| `is_active` | `true` (biased) |
| `password` | SHA-256 hash |
| `avatar_url` | `https://picsum.photos/...` |
| `uuid` | valid v4 UUID |

It's also context-aware: `name` in a `users` table gives person names, in `organizations` — company names, in `products` — product names.

## Config

`seedforge connect` creates a `.seedforge.yaml`:

```yaml
db_url: postgresql://user:pass@localhost:5432/mydb
default_rows: 100
default_schema: public
seed: 42
exclude_tables:
  - _prisma_migrations
  - django_migrations
```

Migration tables (`_prisma_migrations`, `django_migrations`, `alembic_version`, etc.) are excluded automatically.

## Databases

- PostgreSQL (+ CockroachDB)
- MySQL / MariaDB
- SQLite
- Microsoft SQL Server

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
