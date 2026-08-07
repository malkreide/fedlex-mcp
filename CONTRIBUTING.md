# Contributing to fedlex-mcp

[:de: Deutsche Version](CONTRIBUTING.de.md)

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

## The live suite: when it runs, and who sees a red result

**Cadence:** Monday 05:43 UTC, plus on demand via *Actions → Live-Tests → Run
workflow*. See [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Who sees it:** a red run opens an issue titled `Live-Tests gegen fedlex.data.admin.ch rot …`
with the `upstream` label, and comments on the existing one instead of opening a
second. A run that goes green again closes it.

**Three answers, not two.** `scripts/classify_live_run.py` reads the JUnit XML
rather than the exit code and separates `clear` (ran, green), `finding` (ran,
something fell) and `unknown` (did not run — install failed, nothing collected,
everything skipped). An `unknown` never closes an issue: closing would claim a
comparison that never happened.

**A red live run does not necessarily mean *our* bug.** It means the contract
with the source has changed, or the source is down. Both belong seen; only the
first belongs fixed. Please read the run before disabling the job — that is how
this check dies, and it is the only one in the repository that can contradict a
wrong assumption about fedlex.data.admin.ch. Every other test asserts against a fixture, and
the fixture was written from the same assumption as the code.

Not hypothetical: on 2026-07-30 `meteoswiss-mcp`'s first live run in months put
three of six tests on the floor — the endpoint had been retired two days earlier
and nobody had started the suite.

The PR run stays at `-m "not live"`: a foreign 503 must not turn an unrelated
pull request red.
