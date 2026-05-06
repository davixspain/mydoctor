# Changelog

All notable changes to MyDoctor are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] — 2026-05-06 — Initial open-source release

First public release under PolyForm Noncommercial 1.0.0.

### Added

- **Cross-platform installer** (`install.py`): auto-detect OS, guided wizard
  for Linux, macOS, Windows.
- **Telegram bot** (`bot.py`): private bot accepting only the configured
  owner. Supports text, photos, documents, voice messages.
- **Onboarding mode**: triggered by `/start` at first contact, accepts an
  unstructured stream of clinical info (photos, text, voice, PDFs) and
  produces a complete intake summary on demand.
- **Natural language routing**: no slash commands. The bot reads intent from
  free text ("come sto?", "diario", "prossima visita", "reset") and chooses
  the right action via Claude.
- **Obsidian vault template**: structured folders for Visits, Labs,
  Conditions, Differentials, Medications, Diagnostics pending, Doctors,
  Symptom diary, Attachments, Templates. Pre-wired wikilinks and frontmatter.
- **Voice support**: optional local transcription via `faster-whisper`. If
  not installed, audio is archived and the user is asked to summarize in
  text.
- **Proactive review** (`proactive_review.py`):
  - **Weekly** review every Sunday 20:00 — pattern detection over 7 days
    vs the previous 30. Pushes Telegram message only if clinically relevant.
  - **Monthly** review the 1st of each month 20:00 — drift detection over
    30 days vs the previous 90. Same push policy.
- **Service files** for Linux (systemd), macOS (launchd), Windows
  (Task Scheduler).
- **Claude Code skill** (`mydoctor`): structured Italian clinical synthesis
  format (Procedura → Referto → Conclusioni → Quadro complessivo → Domande
  per il medico → Bandiere rosse → In sintesi).
- **Pre-visit briefing**: living document `Prossima visita.md` always up to
  date, ready to print and bring to the doctor.
- **Templates** for new visit, new lab, new differential, new symptom
  episode, daily symptoms.

### Documentation

- Marketing landing copy
- Setup guide
- Architecture overview
- Privacy disclosure
- FAQ
- Troubleshooting guide
- Roadmap (mobile native apps in v2)

### Known limitations

- iOS / Android native apps not yet available (use Telegram client on
  mobile — fully functional).
- Voice transcription requires `faster-whisper` install (~150 MB).
- Claude Code CLI must be installed and authenticated separately.
