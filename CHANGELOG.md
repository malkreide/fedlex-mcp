# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-31

### Added
- Initial release
- **7 tools**: `fedlex_search_laws`, `fedlex_get_law_by_sr`, `fedlex_get_recent_publications`, `fedlex_get_upcoming_changes`, `fedlex_search_gazette`, `fedlex_get_law_history`, `fedlex_search_treaties`
- **2 resources**: `fedlex://sr/{sr_number}`, `fedlex://info`
- SPARQL-powered access to Fedlex linked data endpoint
- 4 language support (de, fr, it, rm)
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud/Render.com)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
- Bilingual documentation (EN/DE)
