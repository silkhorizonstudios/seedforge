# SeedForge

[![PyPI version](https://img.shields.io/pypi/v/seedforge.svg)](https://pypi.org/project/seedforge/)
[![Python](https://img.shields.io/pypi/pyversions/seedforge.svg)](https://pypi.org/project/seedforge/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**One command to fill your database with realistic test data.**

SeedForge connects to your database, reads the schema (tables, columns, foreign keys, constraints), and generates realistic, FK-valid data — no code, no config, no seed scripts.

```bash
pip install seedforge
seedforge connect postgresql://user:pass@localhost/mydb
seedforge generate --rows 1000
# Done. 40 tables filled in 3 seconds.
```

## The Problem

Every developer has been there: you set up a new project, run migrations, open the app — and everything is empty. Dashboards show zeros, lists return nothing, features that depend on data can't be tested.

So you write a seed script. Manually. For every table. And then the schema changes and the script breaks. Or you copy production data into staging — and now you have GDPR problems.

**SeedForge solves this.** It reads your actual database schema, understands the relationships between tables, and generates realistic data that respects all constraints — automatically.

## Features

- **Zero-config** — reads your DB schema automatically, no setup needed
- **FK integrity** — resolves foreign keys via topological sort, inserts in correct order
- **Smart heuristics** — 80+ column name patterns for realistic data (`email` → real email, `price` → decimal, `role` → admin/user/editor)
- **Multi-database** — PostgreSQL, MySQL/MariaDB, SQLite
- **Deterministic** — use `--seed` to get the same data every time, across machines
- **AI (optional)** — plug in Anthropic, OpenAI, Gemini, Groq, or Ollama for extra realism
- **Export** — SQL or JSON file output
- **Privacy-first** — runs entirely locally, your data never leaves your machine

## Why Not Just Ask AI to Generate Data?

You can absolutely paste your schema into ChatGPT and ask it to generate INSERT statements. For a quick one-off with 5 tables, that works fine.

But in practice:

**Scale.** AI generates data token by token. 1,000 rows across 40 tables? That's a 10-minute wait and $2-5 in API costs. SeedForge does it in 2 seconds, free, offline.

**Repeatability.** Every time you ask AI, you get different data. With `seedforge generate --seed 42`, every developer on your team gets identical data, every time. Deterministic. Committable. Reviewable.

**Automation.** You can't put a ChatGPT conversation into your CI/CD pipeline. But you can put `seedforge generate --rows 5000` into a GitHub Action and have fresh test data on every PR.

**Correctness.** AI sometimes forgets a foreign key, generates a duplicate for a UNIQUE column, or invents an ENUM value that doesn't exist. SeedForge reads the actual constraints from your database — it physically can't violate them.

**Cost at scale.** A team of 5 developers, each resetting their local DB 3 times a day:

| | AI API | SeedForge |
|---|---|---|
| Per run | ~$0.50 | $0 |
| Per day (team) | $7.50 | $0 |
| Per month | **$225** | **$0** |

SeedForge uses AI as an optional enhancement for complex data (product descriptions, realistic bios) — not as the engine for every INSERT.

## Installation

```bash
pip install seedforge

# With MySQL support
pip install seedforge[mysql]

# With AI support
pip install seedforge[ai]

# Everything
pip install seedforge[all]
```

## Quick Start

### 1. Connect

```bash
seedforge connect postgresql://user:pass@localhost:5432/mydb

# MySQL
seedforge connect mysql://user:pass@localhost:3306/mydb

# SQLite
seedforge connect sqlite:///path/to/database.db
```

Saves the connection to `.seedforge.yaml` so you don't have to type it again.

### 2. Inspect

```bash
seedforge inspect
```

Shows all tables, columns, types, foreign keys, and insertion order:

```
Found 18 tables (insertion order):

         1. users
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┓
┃ Column     ┃ Type      ┃ Nullable ┃ FK →  ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━┩
│ id         │ serial    │ NO       │       │
│ email      │ varchar   │ NO       │       │
│ name       │ varchar   │ YES      │       │
└────────────┴───────────┴──────────┴───────┘

             2. orders
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Column     ┃ Type      ┃ Nullable ┃ FK →       ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━┩
│ id         │ serial    │ NO       │            │
│ user_id    │ integer   │ NO       │ users.id   │
│ total      │ numeric   │ NO       │            │
└────────────┴───────────┴──────────┴────────────┘
```

### 3. Generate

```bash
# Generate and insert 100 rows per table
seedforge generate --rows 100

# Preview without inserting
seedforge generate --rows 10 --dry-run

# Export to SQL file
seedforge generate --rows 1000 --export sql

# Export to JSON
seedforge generate --rows 1000 --export json

# Deterministic (same data every time)
seedforge generate --rows 100 --seed 42

# Only specific tables (auto-includes FK parents)
seedforge generate --tables orders,payments --rows 50

# Clean tables before generating
seedforge generate --rows 100 --clean
```

### 4. AI Generate (optional)

For maximum realism, SeedForge can use AI to generate context-aware data. Bring your own API key from any supported provider:

```bash
# Auto-detects provider by key prefix
seedforge ai-generate --api-key sk-ant-...   # Anthropic
seedforge ai-generate --api-key sk-...       # OpenAI
seedforge ai-generate --api-key AIza...      # Gemini
seedforge ai-generate --api-key gsk_...      # Groq

# Or set environment variable
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AIza...
export GROQ_API_KEY=gsk_...
export OLLAMA_MODEL=llama3.2      # Local, free

seedforge ai-generate --rows 20

# Explicit provider
seedforge ai-generate --provider ollama --rows 20
```

| Provider | Models | Speed | Cost |
|---|---|---|---|
| **Anthropic** | Claude Haiku, Sonnet, Opus | Fast | $$ |
| **OpenAI** | GPT-4o-mini, GPT-4o | Fast | $$ |
| **Gemini** | Gemini 2.0 Flash | Fast | $ |
| **Groq** | Llama 3.3 70B, Mixtral | Very fast | $ |
| **Ollama** | Any local model | Varies | Free |

## How It Works

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────┐
│  Your DB    │────>│  Schema Reader   │────>│  Dependency   │
│  (PG/MySQL/ │     │  (introspection) │     │  Graph        │
│   SQLite)   │     │                  │     │  (topo sort)  │
└─────────────┘     └──────────────────┘     └──────┬────────┘
                                                     │
                    ┌──────────────────┐              │
                    │  Data Generator  │<─────────────┘
                    │  (heuristics +   │
                    │   optional AI)   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Batch Inserter  │────> Your DB (filled!)
                    │  (FK-valid data) │
                    └──────────────────┘
```

1. **Schema introspection** — connects to your database, reads `information_schema` (or `PRAGMA` for SQLite) to get tables, columns, types, FK relationships, constraints, ENUMs
2. **Dependency graph** — builds a directed graph from FK relationships, runs topological sort to determine insertion order (parents first, children after)
3. **Smart heuristics** — maps column names to appropriate generators using 80+ patterns
4. **FK resolution** — child rows automatically reference real IDs from already-generated parent rows
5. **Batch insert** — fast bulk insertion with proper transaction handling

## Column Name Heuristics

SeedForge automatically detects what kind of data to generate based on column names:

| Column name | Generated data |
|---|---|
| `email` | `john.smith@example.com` |
| `phone`, `mobile` | `+1-555-0123` |
| `first_name` | `John` |
| `last_name` | `Smith` |
| `username` | `jsmith42` |
| `address`, `street` | `123 Main St, Apt 4` |
| `city` | `San Francisco` |
| `country` | `United States` |
| `price`, `amount`, `total` | `49.99` |
| `url`, `website` | `https://example.com` |
| `avatar`, `image_url` | `https://picsum.photos/seed/123/400/300` |
| `role` | `admin`, `user`, `moderator` |
| `status` | `active`, `pending`, `completed` |
| `plan` | `free`, `pro`, `enterprise` |
| `created_at`, `updated_at` | Recent datetime |
| `is_active`, `verified` | `true` (85% bias) |
| `is_deleted`, `archived` | `false` (90% bias) |
| `password` | SHA-256 hash |
| `token`, `api_key` | Random hex string |
| `uuid`, `guid` | Valid UUID v4 |
| ...and 60+ more patterns | |

Context-aware: `name` in a `users` table generates person names, in `organizations` — company names, in `products` — product names.

## Configuration

`.seedforge.yaml` (auto-created by `seedforge connect`):

```yaml
db_url: postgresql://user:pass@localhost:5432/mydb
default_rows: 100
default_schema: public
seed: 42  # optional, for deterministic generation
exclude_tables:
  - _prisma_migrations
  - django_migrations
```

## Supported Databases

- [x] PostgreSQL (psycopg2)
- [x] MySQL / MariaDB (PyMySQL)
- [x] SQLite (built-in)

## Supported AI Providers

- [x] Anthropic (Claude)
- [x] OpenAI (GPT-4o)
- [x] Google Gemini
- [x] Groq (Llama, Mixtral)
- [x] Ollama (local, free)

## Data Privacy

**Your data never leaves your machine.** SeedForge runs entirely locally — it connects directly to your database, generates data in memory, and inserts it. No cloud, no telemetry, no data collection.

When using AI mode, only schema metadata (table and column names) is sent to the AI provider — never your actual data.

## License

MIT

## Contributing

Issues and PRs welcome at [github.com/silkhorizonstudios/seedforge](https://github.com/silkhorizonstudios/seedforge).
