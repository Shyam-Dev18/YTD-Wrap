# ytd-wrap

ytd-wrap — Professional YouTube video downloader with interactive CLI, rich UI, and robust error handling.

## Why this package

ytd-wrap is a professional-grade Python package that demonstrates expertise in:

- CLI-first architecture with clean separation of concerns
- Layered design: CLI -> Core -> Domain -> Infra -> External
- Strict typing, frozen dataclasses, and mypy-oriented code quality
- Optional runtime dependency management and lazy-loading
- Interactive UI with Rich and Questionary
- Robust download pipeline using yt-dlp API
- Cross-platform support (Windows, Linux, macOS)
- Secure, production-ready error handling with custom exception hierarchy
- Pre-release audit workflow: linting, type checking, cleanup, and packaging hygiene

This project is suitable for showcasing Python engineering, open-source design, and production-quality coding skills.

## Architecture

```text
User
	|
	v
CLI Layer (src/ytd_wrap/cli)
	- argparse routing
	- Rich / questionary UI
	- process exit-code boundary
	|
	v
Core Layer (src/ytd_wrap/core)
	- immutable domain models
	- format filtering logic
	- service orchestration via Protocol DI
	|
	v
Infrastructure Layer (src/ytd_wrap/infra)
	- yt-dlp provider adapters
	- ffmpeg detection
	- third-party exception mapping
	|
	v
External Systems
	- yt-dlp library
	- OS environment / ffmpeg binary
```

### Layer rules

- Flow direction is one-way: CLI -> Core -> Infrastructure -> External.
- Core never imports CLI or infra implementation details.
- Infrastructure catches third-party exceptions and raises typed ytd-wrap exceptions.
- CLI owns user-facing rendering and process exit codes.

## Installation

```bash
pip install ytd-wrap
```

## Usage

```bash
# Download a video interactively
ytd-wrap https://www.youtube.com/watch?v=VIDEO_ID

# Check environment
ytd-wrap doctor
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type-check
mypy src/ytd_wrap

# Lint
ruff check src/ tests/
```

## Contribution rules

- Keep architecture boundaries intact; do not add cross-layer shortcuts.
- Domain models in core must remain frozen dataclasses.
- Do not leak raw stack traces to users; route errors through `YtdWrapError` subclasses.
- Keep code offline-testable (mock external services, no network dependency in tests).
- Do not add features without explicit phase scope approval.

## Security note

- Downloads use yt-dlp Python API only; no shell subprocess invocation by ytd-wrap code.
- ffmpeg detection uses `shutil.which` only (no PATH mutation, no auto-install side effects).
- Output template uses yt-dlp metadata template `%(title)s.%(ext)s`; no user-provided filesystem path interpolation.
- Errors shown to end users are sanitized at the CLI boundary (typed messages + optional hint).

## License

MIT
