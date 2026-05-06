# MyDoctor — Public Roadmap

This document tracks committed and planned work across versions. Subject to
revision based on user feedback and market validation.

---

## ✅ Released — v1.0 (2026-05-06) — Initial open-source release

Cross-platform desktop tool under PolyForm Noncommercial 1.0.0.
Mobile via Telegram client.

- Linux / macOS / Windows installer
- Telegram bot with onboarding + natural-language routing
- Obsidian vault skeleton with templates
- Voice / photo / document ingestion
- Proactive weekly + monthly review with Telegram push
- Italian-first clinical synthesis

---

## 🚧 v1.1 — Q3 2026

Quality-of-life improvements based on early feedback.

- **Bilingual support**: English-language vault templates and skill (Italian
  remains primary).
- **Built-in `faster-whisper`** auto-installer in the wizard, so voice
  transcription works out of the box.
- **Vault import** from Apple Health, Google Fit, Withings.
- **Smart attachments**: PDF text extraction (no OCR for image-only PDFs yet).
- **Backup/restore**: encrypted ZIP backup of the entire vault to local /
  external storage on a schedule.
- **OCR** for photographed paper reports via Tesseract integration.

---

## 📅 v2.0 — Out of scope for the open-source release

Native iOS / Android apps were considered but are **out of scope** for this
open-source release. They would require:

- Apple Developer account and ongoing maintenance fee
- Native development (Flutter / Swift / Kotlin)
- App Store / Play Store review for medical-adjacent apps (~2 weeks)
- A backend if the user doesn't have a persistent desktop
- Different licensing model

The Telegram client is a perfectly fine mobile interface for the desktop
bot — and crucially, it works **today** without any additional code.

If you'd like to fork and build a mobile companion under your own
license, that's compatible with the PolyForm Noncommercial license as
long as the result is also non-commercial. For commercial mobile derivatives,
contact the author for a separate license.

---

## 🔮 v3.0 — Possible future directions

Ideas welcomed via [GitHub issues](https://github.com/) — none committed.

- **Family vaults**: shared vault for parent + minor children, with role
  separation
- **GP integration**: secure share-link to send the briefing PDF to a real
  doctor's email or to FSE (Fascicolo Sanitario Elettronico, Italy)
- **Multi-language**: Spanish, German, French with locale-specific
  healthcare workflows
- **Vault formats**: support for Logseq / Roam exports alongside Obsidian

---

## Not planned (intentional scope limits)

- ❌ FDA / CE Class IIa medical device certification — would require massive
  clinical trials and regulatory work.
- ❌ Direct prescriptions or automated diagnoses — explicitly outside
  product scope. MyDoctor prepares the patient for a real doctor; it does
  not replace one.
- ❌ Insurance integration / billing — out of scope.
