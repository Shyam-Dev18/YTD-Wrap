# Changelog

All notable changes to **ytd-wrap** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-03-10

### Changed

- Unified package version source to `ytd_wrap.__version__` so build metadata and runtime version cannot drift.
- Set `__version__ = "1.0.0"` for the new stable release.
- Changed version-check interval from 12 hours to 24 hours to match "once per day" behavior.

## [0.1.0] — 2026-03-03

### Added

#### Project scaffold (Phase 1)
- `pyproject.toml` with PEP 517/518 build configuration (setuptools ≥ 68).
- `ytd_wrap/__init__.py` — package version constant (`__version__ = "0.1.0"`).
- `ytd_wrap/constants.py` — all application-wide magic values:
  - `FORMAT_PRIORITY` sort key for ranking yt-dlp format dicts.
  - `CONTAINER_RULES` mapping codec pairs → preferred container (mp4/mkv/webm).
  - `YTDLP_ERROR_MAP` — 39 lowercase substring → error-code mappings including
    age restriction, geo-block, ffmpeg missing/error, members-only, disk full,
    rate limit, private video, network, and others.
  - `FFMPEG_INSTALL_HINTS` per-OS install instructions.
  - Logging configuration defaults and PyPI API URL constant.
- `ytd_wrap/exceptions.py` — hierarchy: `YtdWrapError` → `DownloadError`,
  `ExtractionError`, `NetworkError`, `DiskFullError`, `UserCancelledError`,
  `FormatSelectionError`, `DependencyMissingError`.
- `ytd_wrap/utils/paths.py` — path helpers:
  - `APP_DIR` / `LOG_DIR` constants (`~/.ytd-wrap/` and `~/.ytd-wrap/logs/`).
  - `ensure_app_dirs()` — creates dirs on startup, swallows `OSError` gracefully.
  - `get_download_dir()` — returns `~/Downloads/` falling back to `~/`.
  - `sanitize_filename()` — strips filesystem-unsafe characters.
  - `get_log_path()` — deterministic log file location.
- `ytd_wrap/utils/logger.py` — `setup_logging()` configures rotating file
  handler (`~/.ytd-wrap/logs/ytd-wrap.log`, 1 MB × 3 backups) and optional
  `DEBUG`-level stream handler when `--debug` is set.
- `ytd_wrap/checks/dependencies.py` — `check_python()`, `check_ytdlp()`,
  `check_ffmpeg()`, `run_all_checks()`, `get_ffmpeg_install_command()`.
- `ytd_wrap/checks/updates.py` — non-blocking once-per-day PyPI version check
  with JSON disk cache (`~/.ytd-wrap/update_cache.json`).
- `tests/` directory — 88 pytest tests covering all infrastructure modules.
- `README.md`, `.gitignore`.

#### UI layer (Phase 3)
- `ytd_wrap/ui/display.py` — Rich-based terminal output:
  - `get_spinner()` — context-manager status spinner.
  - `print_download_start()` — info panel with URL.
  - `print_formats_table()` — Rich table of available video formats.
  - `print_success()` — green panel with saved path.
  - `print_error()` — red panel with message.
  - `print_doctor_table()` — dependency health table with ✓/✗ markers.
  - `print_ffmpeg_missing()` — OS-specific install hint box.
  - `print_update_notice()` — yellow banner for available updates.
- `ytd_wrap/ui/selector.py` — questionary-based interactive picker:
  - `select_format()` — arrow-key format chooser; raises `UserCancelledError`
    on Ctrl-C or empty answer.
  - `confirm_download()` — yes/no confirmation prompt.
- Tests: 136 total (48 new UI-layer tests).

#### Core engine (Phase 4)
- `ytd_wrap/core/resolver.py` — URL classification:
  - `is_social_media(url)` — matches 10 known platform domains.
  - `is_direct_url(url)` — matches `.m3u8`, `.mp4`, `.mkv`, etc.
  - `detect_url_type(url)` → `"social"` | `"direct"` | `"unknown"`.
- `ytd_wrap/core/extractor.py` — yt-dlp metadata/format extraction:
  - `extract_metadata(url)` → dict with `title`, `duration`, `uploader`.
  - `extract_formats(url)` → sorted list of format dicts.
  - `select_best_format(formats)` — picks first entry after priority sort.
  - `determine_output_container(fmt)` — applies `CONTAINER_RULES`.
- `ytd_wrap/core/downloader.py` — yt-dlp download orchestration:
  - `download(url, format_id, title, output_dir, container, hook)` — downloads
    to `<output_dir>/<sanitized_title>.<container>`, strips surrounding quotes
    from URL, cleans up partial `.part` files on failure.
  - `create_progress_hook(progress, task_id, filename)` — Rich progress-bar
    hook; shows truncated filename, speed, ETA; marks ✓ Done / ✗ Failed.
  - `_map_error(msg, url)` — converts yt-dlp error strings to typed exceptions
    with user-friendly hints for age restriction, geo-block, ffmpeg missing,
    members-only, and unavailable content.
- Tests: 203 total (67 new core-engine tests).

#### CLI (Phase 5)
- `ytd_wrap/cli.py` — Click-based entry point:
  - `_SmartGroup` — custom `click.Group` subclass that routes an unknown first
    token as a URL positional argument rather than raising "No such command",
    so `ytd-wrap <url>` and `ytd-wrap doctor` both work correctly.
  - `main` group — `--version / -V` eager flag, epilog with example commands.
  - Social download flow (`_run_social_download`): spinner → metadata +
    formats → Rich format table → arrow-key selection → progress bar download.
    Falls back to `format_id="best"` when no video formats are returned.
  - Direct download flow (`_run_direct_download`): spinner → auto best-format
    selection → progress bar download. Falls back to `"best"` on
    `ExtractionError`.
  - `_handle_download_errors()` — maps every typed exception to a coloured
    error panel and sets the process exit code.
  - `doctor` subcommand — runs dependency checks, prints table; shows
    OS-specific ffmpeg install hint when ffmpeg is missing.
  - Non-blocking update check runs at startup via `check_for_updates()`.
- Tests: 236 total (33 new CLI tests).

#### Edge-case hardening (Phase 6)
- `YTDLP_ERROR_MAP` in `constants.py` expanded from 19 to 39 entries.
- `downloader._map_error` returns descriptive hints for age-restricted,
  geo-blocked, ffmpeg missing/error, members-only, and unavailable content.
- `ensure_app_dirs()` now silently swallows `OSError` and logs a warning
  instead of crashing when the home directory is not writable.
- CLI strips surrounding whitespace and quotes from pasted URLs.
- `create_progress_hook` displays the truncated filename alongside speed/ETA.

[0.1.0]: https://github.com/example/ytd-wrap/releases/tag/v0.1.0
[1.0.0]: https://github.com/example/ytd-wrap/releases/tag/v1.0.0
