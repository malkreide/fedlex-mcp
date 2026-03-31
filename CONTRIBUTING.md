# Contributing to fedlex-mcp

Thank you for your interest in contributing! This server is part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide).

---

## Reporting Issues

Use [GitHub Issues](https://github.com/malkreide/fedlex-mcp/issues) to report bugs or request features.

Please include:
- Python version and OS
- Full error message or description of unexpected behaviour
- Steps to reproduce

---

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `PYTHONPATH=src pytest tests/ -m "not live"`
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/): `feat: add new tool`
6. Push and open a Pull Request against `main`

---

## Code Style

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Type hints required for all public functions
- Tests required for new tools (`tests/test_server.py`)
- Follow the existing FastMCP / Pydantic v2 patterns in `server.py`

---

## Data Source

This server uses the public Fedlex SPARQL endpoint — no authentication required.

| Source | Documentation |
|--------|--------------|
| Fedlex SPARQL | [fedlex.data.admin.ch](https://fedlex.data.admin.ch/) |
| JOLux Ontology | [Fedlex data model](https://fedlex.data.admin.ch/) |

When adding new SPARQL queries, verify them manually against the endpoint first and handle edge cases (missing optional fields, timeout on broad queries).

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
