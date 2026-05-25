# Contributing to SeedForge

Thanks for your interest in contributing! Here's how to get started.

## How to Contribute

### 1. Fork the repository

Click "Fork" on [github.com/silkhorizonstudios/seedforge](https://github.com/silkhorizonstudios/seedforge).

### 2. Clone your fork

```bash
git clone https://github.com/YOUR_USERNAME/seedforge.git
cd seedforge
pip install -e ".[all]"
```

### 3. Create a branch

```bash
git checkout -b feature/your-feature-name
```

Use a descriptive branch name:
- `feature/mongodb-support`
- `fix/fk-resolution-bug`
- `docs/add-examples`

### 4. Make your changes

- Write clean, readable code
- Follow existing code style
- Add tests for new features
- Run tests before submitting:

```bash
python -m pytest tests/ -v
```

### 5. Commit

```bash
git add -A
git commit -m "Add MongoDB support"
```

Write clear, concise commit messages. One line, imperative mood.

### 6. Push and create a Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub against the `main` branch.

## Pull Request Guidelines

- **One PR = one feature/fix.** Don't mix unrelated changes.
- **Describe what and why** in the PR description.
- **All tests must pass** before merge.
- **Squash merge** will be used — your commits will be combined into one clean commit on `main`.
- PRs require **at least 1 approval** before merging.

## What We're Looking For

- New database support (MongoDB, CockroachDB, etc.)
- New column heuristics (more patterns for realistic data)
- Performance improvements
- Bug fixes
- Documentation improvements
- Tests

## Code Structure

```
seedforge/
├── cli.py            # CLI commands (Typer)
├── introspector.py   # DB schema readers (PostgreSQL, MySQL, SQLite)
├── graph.py          # FK dependency graph + topological sort
├── generators.py     # Data generation engine
├── heuristics.py     # Column name → generator mapping (80+ patterns)
├── inserter.py       # Batch INSERT (multi-DB)
├── ai.py             # Optional AI generation (multi-provider)
├── config.py         # .seedforge.yaml handling
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific file
python -m pytest tests/test_heuristics.py -v
```

Tests don't require a database connection — they test heuristics, graph logic, and generators in isolation.

## Questions?

Open an [issue](https://github.com/silkhorizonstudios/seedforge/issues) and we'll help.
