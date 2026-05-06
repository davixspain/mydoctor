"""MyDoctor — review proattivo settimanale/mensile.

Lancia Claude Code in modalità non interattiva, gli chiede di scansionare
il vault Obsidian per trovare pattern temporali (alimento→sintomo, cluster,
drift) e, se Claude trova qualcosa di clinicamente rilevante, spedisce il
risultato via Telegram all'OWNER chat_id usando l'API Bot.

Schedulato dal sistema operativo:
    Linux  → systemd user timer
    macOS  → launchd plist con StartCalendarInterval
    Windows → Task Scheduler trigger

Path neutri: tutti i percorsi sono parametrizzati via variabili d'ambiente.
Vedi src/bot.py per la documentazione completa delle env vars.

Uso manuale:
    venv/bin/python src/proactive_review.py --mode weekly
    venv/bin/python src/proactive_review.py --mode monthly
    venv/bin/python src/proactive_review.py --mode weekly --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# ── Paths (cross-platform) ────────────────────────────────────────────────────
def _default_home() -> Path:
    return Path.home() / "MyDoctor"


_env_home = os.environ.get("MYDOCTOR_HOME", "").strip()
MYDOCTOR_HOME = Path(_env_home) if _env_home else _default_home()
load_dotenv(MYDOCTOR_HOME / ".env")
_env_home = os.environ.get("MYDOCTOR_HOME", "").strip()
if _env_home:
    MYDOCTOR_HOME = Path(_env_home)

VAULT = MYDOCTOR_HOME / "vault"
LOG_DIR = MYDOCTOR_HOME / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_claude() -> Path:
    env_bin = os.environ.get("CLAUDE_BIN", "").strip()
    if env_bin:
        return Path(env_bin)
    found = shutil.which("claude")
    if found:
        return Path(found)
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".local" / "bin" / "claude.exe",
        Path("/usr/local/bin/claude"),
        Path("C:/Program Files/Claude/claude.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("claude")


CLAUDE_BIN = _resolve_claude()

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN = os.getenv("MYDOCTOR_BOT_TOKEN", "").strip()
OWNER = int(os.getenv("MYDOCTOR_OWNER_CHAT_ID", "0") or "0")
TIMEOUT = int(os.getenv("MYDOCTOR_REVIEW_TIMEOUT", "900"))
DISABLE_PUSH = os.getenv("MYDOCTOR_DISABLE_PROACTIVE_PUSH", "0").strip() == "1"

NOTHING_MARKER = "[NIENTE_DI_RILEVANTE]"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("review")


# ── Prompts ───────────────────────────────────────────────────────────────────
def build_weekly_prompt() -> str:
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    return f"""[REVIEW SETTIMANALE NON INTERATTIVA — agente proattivo]

Skill `mydoctor` attiva. Vault in {VAULT}.

CONTESTO. L'utente non ha la memoria di cosa ha mangiato due mesi fa né di
quante volte ha avuto un certo sintomo. Tu sì, perché hai accesso al diario
completo. Il tuo compito qui è scansionare proattivamente l'ultima settimana
e produrre eventuali allarmi/osservazioni che lui non noterebbe da solo.

COMPITO:
1. Leggi il vault `Profile.md` se non lo conosci ancora (anagrafica, baseline).
2. Leggi `vault/Symptom diary/` — tutte le note datate >= {week_ago}.
   (Includi anche `_review_*.md` precedenti se utili al confronto.)
3. Confronta con i 30 giorni precedenti ({month_ago} – {week_ago}).
4. Cerca:
   - Pattern alimento → sintomo (cibo X correlato a sintomo Y entro 6–24 ore,
     con almeno 2 ricorrenze nella finestra di osservazione)
   - Cluster temporali di sintomi (es. 3 episodi GI in 4 giorni)
   - Reazioni allergiche orofaringee anche lievi
   - Segni di pericolo: melena, ematochezia, vomito, calo ponderale, dolore
     epigastrico severo, sintomi anafilattoidi
   - Drift di severità o frequenza (peggioramento progressivo)
   - Aderenza/non-aderenza a trial dietetici/terapeutici proposti
   - Esami programmati nella `Prossima visita.md` ancora non eseguiti

OUTPUT — REGOLE FERREE:
- Se NON trovi NULLA di clinicamente rilevante o nuovo, rispondi SOLO con la
  stringa esatta `{NOTHING_MARKER}` su una riga, senza preamboli e senza altro.
- Se trovi qualcosa, produci un messaggio Telegram (massimo 3500 caratteri)
  in italiano, formato:

📊 *Riepilogo settimanale {week_ago.strftime('%d/%m')}–{today.strftime('%d/%m')}*

*Pattern osservati*:
• ...
• ...

*Drift / nuovi elementi*: ...

*Da portare al medico*: ...

*Bandiere rosse*: nessuna / ...

REGISTRAZIONE NEL VAULT (sempre, anche se [NIENTE_DI_RILEVANTE]):
5. Crea/sovrascrivi `vault/Symptom diary/_review_settimanale_{today}.md` con
   frontmatter type=review e tag `#review-settimanale`. Se trovato qualcosa,
   includi la sintesi completa con wikilink alle note origine. Se nulla,
   nota breve.
6. Aggiorna `00 Home.md` aggiungendo (se non c'è) un link alla review.
"""


def build_monthly_prompt() -> str:
    today = datetime.now().date()
    month_ago = today - timedelta(days=30)
    quarter_ago = today - timedelta(days=90)
    return f"""[REVIEW MENSILE NON INTERATTIVA — drift detection]

Skill `mydoctor` attiva. Vault in {VAULT}.

CONTESTO. Cerchi tendenze su orizzonte lungo (30+ giorni) che le review
settimanali singolarmente non vedono.

COMPITO:
1. Leggi `Profile.md` per il contesto del paziente.
2. Leggi `vault/Symptom diary/` — tutte le note degli ultimi 30 giorni
   (>= {month_ago}) + le `_review_settimanale_*.md` del periodo.
3. Confronta col mese precedente ({quarter_ago} – {month_ago}).
4. Cerca:
   - Drift di frequenza dei sintomi (aumento/diminuzione nel tempo)
   - Drift di severità
   - Cluster nuovi (ondate di episodi simili)
   - Calo ponderale silenzioso (se l'utente ha registrato il peso)
   - Correlazioni stagionali, con stress, con eventi di vita
   - Diagnosi differenziali \"dormienti\" da riaprire alla luce di nuovi dati
   - Stato dei test programmati: quali eseguiti, quali ancora pendenti
   - Aderenza al piano alimentare/terapeutico

OUTPUT — REGOLE FERREE:
- Se nulla di rilevante → SOLO `{NOTHING_MARKER}`.
- Se rilevante → messaggio Telegram (max 3500 char):

📈 *Review mensile {month_ago.strftime('%d/%m')}–{today.strftime('%d/%m')}*

*Drift osservato*:
• frequenza sintomi: ...
• severità: ...

*Nuove correlazioni / pattern emergenti*: ...

*Test programmati — stato*:
• [✓/✗] ...

*Diagnosi differenziali da rivisitare*: ...

*Raccomandazione operativa*: ...

REGISTRAZIONE NEL VAULT (sempre):
5. Crea `vault/Symptom diary/_review_mensile_{today}.md` con tag `#review-mensile`.
6. Se hai trovato pattern rilevanti, aggiorna le note pertinenti in
   `Conditions/`, `Differentials/`, `Prossima visita.md`.
"""


# ── Claude bridge ─────────────────────────────────────────────────────────────
def call_claude(prompt: str) -> str:
    """Run Claude with a fresh session (so it doesn't conflict with chat)."""
    if not CLAUDE_BIN.exists():
        log.error("claude binary missing at %s", CLAUDE_BIN)
        return ""
    sid = str(uuid.uuid4())
    cmd = [
        str(CLAUDE_BIN),
        "--session-id", sid,
        "--dangerously-skip-permissions",
        "-p", prompt,
    ]
    log.info(
        "calling claude (sid=%s, prompt=%d chars, timeout=%ds)",
        sid[:8], len(prompt), TIMEOUT,
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(MYDOCTOR_HOME),
            capture_output=True,
            timeout=TIMEOUT,
            text=True,
        )
    except subprocess.TimeoutExpired:
        log.error("claude timed out after %ds", TIMEOUT)
        return ""
    if proc.returncode != 0:
        log.error("claude exit %s: %s", proc.returncode, (proc.stderr or "")[-500:])
        return ""
    return (proc.stdout or "").strip()


# ── Telegram push ─────────────────────────────────────────────────────────────
def chunked(text: str, size: int = 4000) -> list[str]:
    """Split a long response into Telegram-safe chunks at newline boundaries."""
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= size:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, size)
        if cut < size // 2:
            cut = size
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts


def send_telegram(text: str, parse_mode: str | None = "Markdown") -> bool:
    """POST to Telegram sendMessage. Falls back to plain text on parse error."""
    if not TOKEN or OWNER == 0:
        log.error("Telegram TOKEN/OWNER not configured — cannot push")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload: dict[str, str] = {"chat_id": str(OWNER), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        if body.get("ok"):
            return True
        log.warning("telegram replied non-ok: %s", body)
        if parse_mode:
            log.info("retrying without parse_mode")
            return send_telegram(text, parse_mode=None)
        return False
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace") if exc.fp else ""
        log.error("telegram HTTP %s: %s", exc.code, body[:300])
        if parse_mode and "can't parse" in body.lower():
            return send_telegram(text, parse_mode=None)
        return False
    except urllib.error.URLError as exc:
        log.error("telegram URL error: %s", exc)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["weekly", "monthly"], required=True)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="non inviare a Telegram, stampa solo l'output di Claude",
    )
    args = parser.parse_args()

    if args.mode == "weekly":
        prompt = build_weekly_prompt()
    else:
        prompt = build_monthly_prompt()

    output = call_claude(prompt)
    if not output:
        log.warning("empty output from claude (mode=%s)", args.mode)
        return 1

    is_nothing = NOTHING_MARKER in output
    log.info("review %s: %d chars output, has_nothing_marker=%s",
             args.mode, len(output), is_nothing)

    if args.dry_run:
        print(f"--- DRY RUN ({args.mode}) ---")
        print(output)
        return 0

    if is_nothing:
        log.info("review %s: nothing notable, skipping Telegram push", args.mode)
        return 0

    if DISABLE_PUSH:
        log.info("review %s: PROACTIVE_PUSH disabled, skipping Telegram", args.mode)
        return 0

    sent = 0
    chunks = chunked(output)
    for chunk in chunks:
        if send_telegram(chunk):
            sent += 1
    log.info("review %s: pushed %d/%d chunks to telegram",
             args.mode, sent, len(chunks))
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
