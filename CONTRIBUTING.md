# Contributing to MyDoctor

Thanks for taking the time to contribute. This is a side project, so I
can't promise SLA-grade responsiveness, but I read every issue and PR.

## Ground rules

1. **Privacy first.** Never include real health data in issues, PRs, logs,
   or screenshots. If you must share an example, anonymize first or
   construct a synthetic case.
2. **Italian primary, English welcome.** The skill and prompts default to
   Italian because that's what the original case was in. English
   contributions are very welcome — see "Localization" below.
3. **No medical claims.** Don't add features that could be interpreted as
   making diagnoses, prescribing treatments, or replacing a physician.
   Anything that could nudge a user toward a clinical decision must be
   framed as "to discuss with your doctor", never as "do this".

## How to contribute

### Bug reports

Open an issue with:

- OS + version
- Python + Claude Code versions
- Steps to reproduce
- Expected vs actual behavior
- Relevant log lines (anonymized!)

There's an issue template in `.github/ISSUE_TEMPLATE/bug_report.md`.

### Feature requests

Use the feature request template. Before opening, check
[`ROADMAP.md`](ROADMAP.md) — your idea may already be planned.

### Pull requests

Fork → branch → PR. For non-trivial changes, open an issue first to
discuss the approach.

PR checklist:

- [ ] Tested on at least one of Linux/macOS/Windows
- [ ] Updated docs if behavior changed
- [ ] No real health data in commits, fixtures, or examples
- [ ] Lint clean (`ruff check src/` if you use ruff)
- [ ] Conventional commit message preferred (`feat:`, `fix:`, `docs:`,
      `refactor:`, `chore:`)

### Areas where help is particularly appreciated

- 🌍 **Localization**: English, Spanish, German, French versions of
  the skill, vault templates, and bot prompts. Each language is a
  separate flavor — keep file structure identical, just translate
  contents.
- 🪟 **macOS / Windows install testing** — I primarily develop on
  Linux. macOS launchd plist edge cases and Windows Task Scheduler
  quirks are an underserved area.
- 📄 **OCR for paper-only PDFs** — current pipeline reads images
  visually via Claude vision but cannot extract searchable text from
  scanned PDFs. Tesseract integration would unlock retroactive search.
- 🔄 **Imports from health platforms** — Apple Health, Google Fit,
  Withings, glucose meters. Anything that has a structured export.
- 🔐 **Encrypted backup automation** — `restic` / `borg` wrappers
  with sane defaults for the vault.

## Code style

- Python 3.10+ syntax (use `|` for union types, `list[str]` etc.)
- Type hints on public functions
- Docstrings on modules and non-obvious functions
- `from __future__ import annotations` at the top of every Python file
- 100 char line limit (soft), 120 max
- Standard library preferred where reasonable; minimize dependencies

## Testing

There's no formal test suite yet — the project grew organically from a
working prototype. If you want to add tests, please do. Suggested
structure:

```
tests/
├── test_install.py        # OS detection, path resolution, prereq checks
├── test_bot_helpers.py    # diary helpers, attachment routing, reset detection
├── test_review.py         # weekly/monthly prompt builders, parsing
└── fixtures/              # synthetic vault for integration tests
```

## Releases

Versioning follows semver:

- **Patch** (1.0.x): bug fixes, doc updates, minor tweaks
- **Minor** (1.x.0): new features, no breaking changes
- **Major** (x.0.0): breaking changes to vault structure, config, or CLI

Release process: tag → write changelog entry → push → GitHub release.

## Code of conduct

Be kind. Be technical. Disagree about ideas, not about people. See
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License of contributions

By submitting a PR you agree that your contribution will be licensed
under the same [PolyForm Noncommercial 1.0.0](LICENSE.md) as the rest of
the project, with the author retaining the right to relicense for
commercial purposes.
