"""MyDoctor — Telegram bot privato cross-platform.

Pipeline:
    Telegram → bot.py → subprocess Claude Code → vault Obsidian → Telegram

La skill `mydoctor` (installata in ~/.claude/skills/mydoctor/) si auto-attiva
nella working directory del prodotto. Una sola sessione Claude persistente
(--resume) per conservare la conversazione fra messaggi.

Path neutri: tutti i percorsi sono parametrizzati via variabili d'ambiente:
    MYDOCTOR_HOME       root del prodotto installato
                        default: $HOME/MyDoctor (Linux/macOS) o
                                 %USERPROFILE%\\MyDoctor (Windows)
    CLAUDE_BIN          path completo del binario claude
                        default: cercato in PATH (`shutil.which`)
    MYDOCTOR_BOT_TOKEN  token del bot Telegram (obbligatorio)
    MYDOCTOR_OWNER_CHAT_ID  chat_id del proprietario (obbligatorio)
    MYDOCTOR_TIMEOUT    timeout per chat interattiva (default 480s)

Avvio dev:    venv/bin/python src/bot.py
Avvio prod:   gestito da systemd (Linux) / launchd (macOS) / Task Scheduler (Windows)
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Paths (cross-platform, no hardcoded values) ───────────────────────────────
def _default_home() -> Path:
    """Default install location, OS-aware."""
    return Path.home() / "MyDoctor"


# Risolvo MYDOCTOR_HOME prima di caricare il .env del prodotto, perché potrebbe
# essere in MYDOCTOR_HOME stesso. Strategia: se MYDOCTOR_HOME è già nell'env,
# uso quello; altrimenti uso il default e cerco lì il .env.
_env_home = os.environ.get("MYDOCTOR_HOME", "").strip()
MYDOCTOR_HOME = Path(_env_home) if _env_home else _default_home()
load_dotenv(MYDOCTOR_HOME / ".env")
# Re-leggo il .env in caso definisca MYDOCTOR_HOME diversamente
_env_home = os.environ.get("MYDOCTOR_HOME", "").strip()
if _env_home:
    MYDOCTOR_HOME = Path(_env_home)

VAULT = MYDOCTOR_HOME / "vault"
ATTACHMENTS = VAULT / "Attachments"
DIARY = VAULT / "Symptom diary"
LOG_DIR = MYDOCTOR_HOME / "logs"
SESSION_FILE = MYDOCTOR_HOME / ".session_id"
ONBOARDING_FLAG = MYDOCTOR_HOME / ".onboarding"

# Claude binary: prima env var, poi PATH lookup, poi fallback comune
def _resolve_claude() -> Path:
    env_bin = os.environ.get("CLAUDE_BIN", "").strip()
    if env_bin:
        return Path(env_bin)
    found = shutil.which("claude")
    if found:
        return Path(found)
    # Fallbacks per OS comuni
    candidates = [
        Path.home() / ".local" / "bin" / "claude",  # Linux/macOS
        Path.home() / ".local" / "bin" / "claude.exe",  # Windows
        Path("/usr/local/bin/claude"),
        Path("C:/Program Files/Claude/claude.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("claude")  # ultima istanza, fallirà con messaggio chiaro


CLAUDE_BIN = _resolve_claude()

# Crea le cartelle necessarie (idempotente)
for d in (MYDOCTOR_HOME, LOG_DIR, ATTACHMENTS, DIARY):
    d.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN = os.getenv("MYDOCTOR_BOT_TOKEN", "").strip()
OWNER = int(os.getenv("MYDOCTOR_OWNER_CHAT_ID", "0") or "0")
TIMEOUT = int(os.getenv("MYDOCTOR_TIMEOUT", "480"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = LOG_DIR / "mydoctor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("mydoctor")
try:
    LOG_FILE.chmod(0o600)
except OSError:
    pass

# Silenzio i log noisy del client Telegram
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)


# ── Session persistence ───────────────────────────────────────────────────────
def load_sid() -> str | None:
    try:
        s = SESSION_FILE.read_text().strip()
        return s or None
    except OSError:
        return None


def save_sid(sid: str) -> None:
    SESSION_FILE.write_text(sid)
    try:
        SESSION_FILE.chmod(0o600)
    except OSError:
        pass


def clear_sid() -> None:
    try:
        SESSION_FILE.unlink()
    except FileNotFoundError:
        pass


# ── Auth ──────────────────────────────────────────────────────────────────────
def is_owner(chat_id: int) -> bool:
    return OWNER != 0 and chat_id == OWNER


# ── Onboarding state ──────────────────────────────────────────────────────────
def is_onboarding() -> bool:
    return ONBOARDING_FLAG.exists()


def set_onboarding(active: bool) -> None:
    if active:
        ONBOARDING_FLAG.touch()
        try:
            ONBOARDING_FLAG.chmod(0o600)
        except OSError:
            pass
    else:
        try:
            ONBOARDING_FLAG.unlink()
        except FileNotFoundError:
            pass


def onboarding_prefix() -> str:
    """Prefix prepended to every Claude call while onboarding is active."""
    if not is_onboarding():
        return ""
    return (
        "[ONBOARDING IN CORSO] L'utente ha appena avviato la sessione e sta "
        "caricando informazioni cliniche storiche (foto, testo, vocali, PDF). "
        "Comportamento richiesto durante l'onboarding:\n"
        "1) Per ogni pezzo di informazione che arriva: leggilo, classificalo "
        "(referto/sintomo/allergia/farmaco/visita/operatore/foto sintomatica), "
        "estrai i dati strutturati e archivialo nella cartella corretta del "
        "vault. Crea nuove note in Visits/, Labs/, Conditions/, Differentials/, "
        "Medications/, Doctors/, Symptom diary/. Aggiorna Timeline.md, "
        "00 Home.md, Profile.md (compila i campi del template) e i file di "
        "memoria.\n"
        "2) Riconcilia con i dati già presenti — non duplicare, integra.\n"
        "3) Ringrazia brevemente e segnala in 1-2 frasi cosa hai catalogato "
        "(es. \"OK, ho registrato il referto della tiroide del 2023 in "
        "Labs/\"). NON fare interrogatori lunghi.\n"
        "4) Quando l'utente dice \"basta\" / \"finito\" / \"ho finito di "
        "caricare\" / \"ok stop\" / \"chiudi\" / equivalenti, fai la SINTESI "
        "FINALE del caso, strutturata come un internista al primo consulto:\n"
        "   • Anagrafica e contesto (1 riga)\n"
        "   • Anamnesi patologica remota (cronologica)\n"
        "   • Anamnesi patologica prossima (problemi attivi)\n"
        "   • Anamnesi farmacologica + allergie\n"
        "   • Anamnesi familiare (se nota)\n"
        "   • Stile di vita rilevante (alcol, fumo, attività, dieta)\n"
        "   • Esami eseguiti — riassunto risultati chiave\n"
        "   • Differenziali aperti con likelihood (alta/media/bassa)\n"
        "   • Test mancanti da richiedere (con razionale)\n"
        "   • Bandiere rosse di sicurezza\n"
        "   • Domande prioritarie per il prossimo medico curante\n"
        "   • In sintesi: 3-4 frasi chiave\n"
        "   Termina la risposta con la stringa esatta `[ONBOARDING_COMPLETE]` "
        "su una riga a parte (la rilevo io e disattivo la modalità).\n\n"
    )


# ── Claude bridge ─────────────────────────────────────────────────────────────
PRIMER = (
    "[MyDoctor mode] Stai parlando con l'utente via Telegram dal suo bot "
    f"privato. Skill `mydoctor` attiva. Working directory: {MYDOCTOR_HOME}.\n"
    f"**Vault Obsidian** in {VAULT} è la fonte di verità storica del caso "
    "clinico. Profile.md contiene i dati anagrafici dell'utente — leggilo "
    "all'inizio se non lo conosci ancora.\n\n"
    "Il bot NON ha slash command (a parte /start gestito da Telegram): tu "
    "(Claude) interpreti l'intent dal linguaggio naturale e scegli da solo "
    "l'azione giusta. Esempi:\n"
    "• \"come sto?\" / \"riepilogo\" / \"stato\" → leggi 00 Home.md + Prossima "
    "visita.md e dai un riepilogo conciso (max 8 righe).\n"
    "• \"diario\" / \"diario di oggi\" → leggi vault/Symptom diary/<oggi>.md e "
    "mostralo (creandolo se manca con il template di Templates/Daily symptoms.md).\n"
    "• \"prossima visita\" / \"briefing\" / \"domande per il medico\" → mostra "
    "vault/Prossima visita.md.\n"
    "• \"vault\" / \"cosa c'è nel vault\" → riassumi numero di visite/labs/"
    "differenziali/note di diario.\n"
    "• Domande cliniche libere → rispondi con il formato strutturato della skill.\n\n"
    "Quando arrivano foto/documenti via Telegram il bot li salva già in "
    "vault/Attachments/YYYY-MM-DD/ e aggiorna vault/Symptom diary/YYYY-MM-DD.md "
    "con l'embed e un placeholder \"_(in attesa di valutazione)_\". Tu devi: "
    "(1) analizzare il file con Read, (2) sostituire il placeholder con la "
    "valutazione strutturata, (3) creare nuove note in Visits/ o Labs/ se è un "
    "referto formale, (4) aggiornare Conditions/, Differentials/, Prossima "
    "visita.md, Timeline.md, 00 Home.md, e i file di memoria.\n\n"
    "**[CORRELAZIONE TEMPORALE AUTOMATICA — sempre attiva]**\n"
    "Ogni volta che arriva un nuovo dato (foto, sintomo, referto, pasto, vocale), "
    "PRIMA di rispondere all'utente tu devi:\n"
    "(a) listare i file in vault/Symptom diary/ degli ultimi 60 giorni e "
    "leggere i 5–10 più recenti rilevanti;\n"
    "(b) cercare correlazioni alimento→sintomo entro 6–24 ore (es. \"ogni volta "
    "che mangia kebab compare diarrea il mattino dopo\"), cluster temporali, "
    "drift di severità, e segni di pericolo (melena, ematochezia, anafilassi, "
    "calo ponderale);\n"
    "(c) se trovi un pattern con ≥2 ricorrenze, NOMINALO esplicitamente nella "
    "tua risposta come \"📊 Pattern osservato:\" anche se l'utente non lo "
    "chiede; se non c'è niente di nuovo, non forzare correlazioni assenti.\n"
    "L'utente non ha la memoria di quello che ha mangiato 2 mesi fa: tu sì. "
    "È il tuo compito principale rilevare i pattern che lui non vede.\n\n"
    "Risposta sempre in italiano clinico. Telegram ha 4096 caratteri per "
    "messaggio: sii completo ma essenziale.\n\n"
    "Utente:\n"
)

ONBOARDING_DONE_MARKER = "[ONBOARDING_COMPLETE]"


async def call_claude(prompt: str) -> str:
    """Run Claude Code in MYDOCTOR_HOME, resuming the persistent session."""
    if not CLAUDE_BIN.exists():
        return (
            f"❌ binario claude non trovato in {CLAUDE_BIN}.\n"
            "Installa Claude Code da https://claude.com/claude-code "
            "e poi imposta CLAUDE_BIN nel file .env."
        )

    sid = load_sid()
    fresh = sid is None
    if fresh:
        sid = str(uuid.uuid4())

    flag = "--session-id" if fresh else "--resume"
    full_prompt = PRIMER + onboarding_prefix() + prompt
    cmd = [
        str(CLAUDE_BIN),
        flag, sid,
        "--dangerously-skip-permissions",
        "-p", full_prompt,
    ]
    log.info(
        "call_claude: fresh=%s sid=%s onboarding=%s prompt=%r",
        fresh, sid[:8], is_onboarding(), prompt[:80],
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(MYDOCTOR_HOME),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return f"⏱️ Timeout {TIMEOUT}s — riprova con domanda più mirata."

    out = (stdout or b"").decode("utf-8", errors="replace").strip()
    err = (stderr or b"").decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        log.error("claude exit %s: %s", proc.returncode, err[-400:])
        return (
            f"❌ Errore claude (exit {proc.returncode}). "
            "Scrivi \"reset\" per ricominciare la conversazione."
        )

    if out:
        save_sid(sid)

    if is_onboarding() and ONBOARDING_DONE_MARKER in out:
        set_onboarding(False)
        out = out.replace(ONBOARDING_DONE_MARKER, "").strip()
        log.info("onboarding completed by Claude marker")
        out += (
            "\n\n✅ Onboarding completato. D'ora in poi parlami normalmente: "
            "domande, foto di referti nuovi, sintomi del giorno, qualsiasi cosa."
        )

    return out or "(nessun output)"


# ── Vault helpers ─────────────────────────────────────────────────────────────
def attachment_dir(date_obj: datetime) -> Path:
    """Return (and create) the attachments directory for a given day."""
    d = ATTACHMENTS / date_obj.strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def diary_file(date_obj: datetime) -> Path:
    """Return the diary note path for a given day (does not create it)."""
    return DIARY / f"{date_obj.strftime('%Y-%m-%d')}.md"


def ensure_diary_note(date_obj: datetime) -> Path:
    """Create the diary note for the day if it does not exist yet."""
    p = diary_file(date_obj)
    if p.exists():
        return p
    iso = date_obj.strftime("%Y-%m-%d")
    it = date_obj.strftime("%d/%m/%Y")
    p.write_text(
        f"---\n"
        f"type: diary\n"
        f"date: {iso}\n"
        f"tags: [diario, sintomo]\n"
        f"---\n\n"
        f"# Diario sintomi — {it}\n\n"
        f"## Pasti del giorno (e della sera prima)\n\n"
        f"_(da compilare)_\n\n"
        f"## Evacuazioni\n\n"
        f"_(da compilare)_\n\n"
        f"## Sintomi GI / orofaringei / altri\n\n"
        f"_(da compilare)_\n\n"
        f"## Allegati e valutazione\n\n"
    )
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return p


def append_attachment_to_diary(
    date_obj: datetime, attachment_filename: str, kind: str, caption: str = "",
) -> Path:
    """Append an attachment embed to today's diary note. Returns the diary path."""
    p = ensure_diary_note(date_obj)
    iso = date_obj.strftime("%Y-%m-%d")
    hhmm = date_obj.strftime("%H:%M")
    embed_line = (
        f"![[../Attachments/{iso}/{attachment_filename}]]"
        if kind in ("foto",)
        else f"[[../Attachments/{iso}/{attachment_filename}]]"
    )
    block = (
        f"\n### {hhmm} — {kind} ricevuto via Telegram\n\n"
        f"{embed_line}\n"
    )
    if caption:
        block += f"\n**Caption**: {caption}\n"
    block += "\n_(in attesa di valutazione)_\n"
    with p.open("a") as fh:
        fh.write(block)
    return p


# ── Telegram helpers ──────────────────────────────────────────────────────────
def split_chunks(text: str, size: int = 4000) -> list[str]:
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


async def keep_typing(chat, done: asyncio.Event) -> None:
    """Send 'typing...' every 4s until done is set (prevents UI timeout)."""
    while not done.is_set():
        try:
            await chat.send_chat_action("typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(done.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


async def reply_long(update: Update, text: str) -> None:
    for chunk in split_chunks(text):
        await update.message.reply_text(chunk)


async def with_typing(update, coro):
    """Run a coroutine while showing 'typing...' in Telegram."""
    done = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(update.effective_chat, done))
    try:
        return await coro
    finally:
        done.set()
        try:
            await asyncio.wait_for(typing_task, timeout=2)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass


# ── Voice transcription (best-effort, opt-in) ─────────────────────────────────
def _try_transcribe(audio_path: Path) -> str | None:
    """Best-effort local transcription via faster-whisper / openai-whisper / whisper CLI."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(str(audio_path), language="it")
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if text:
            return text
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("faster-whisper failed: %s", exc)

    try:
        import whisper  # type: ignore
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path), language="it")
        text = (result.get("text") or "").strip()
        if text:
            return text
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("openai-whisper failed: %s", exc)

    if shutil.which("whisper"):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                proc = subprocess.run(
                    ["whisper", str(audio_path), "--language", "it",
                     "--output_format", "txt", "--output_dir", tmp,
                     "--model", "base"],
                    capture_output=True, timeout=300, check=False,
                )
                if proc.returncode == 0:
                    txts = list(Path(tmp).glob("*.txt"))
                    if txts:
                        return txts[0].read_text().strip() or None
        except Exception as exc:  # noqa: BLE001
            log.warning("whisper CLI failed: %s", exc)
    return None


# ── Reset detection (no slash commands) ───────────────────────────────────────
RESET_PHRASES = {
    "reset", "ricomincia", "ricomincia da capo", "nuova sessione",
    "azzera sessione", "azzera la sessione", "ricominciamo",
    "ricominciamo da capo", "fresh start", "nuova chat",
}


def _is_reset_request(text: str) -> bool:
    t = text.strip().lower().rstrip("!?. ")
    return t in RESET_PHRASES


# ── Handlers ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — Telegram lo invia automaticamente al primo contatto."""
    chat_id = update.effective_chat.id
    if not is_owner(chat_id):
        await update.message.reply_text(
            f"❌ Bot privato.\nChat ID rilevato: {chat_id}\n"
            f"Se sei il proprietario, aggiungi questo ID a "
            f"MYDOCTOR_OWNER_CHAT_ID nel file .env e riavvia il bot."
        )
        log.warning("rejected access from chat_id=%s", chat_id)
        return

    clear_sid()
    set_onboarding(True)
    log.info("/start by owner — onboarding mode activated, session cleared")

    await update.message.reply_text(
        "🩺 *MyDoctor attivo.*\n\n"
        "Sono il tuo assistente clinico personale. Per partire ho bisogno di "
        "raccogliere TUTTO quello che hai sul tuo caso. Mandami senza ordine, "
        "uno alla volta o a raffica:\n\n"
        "📷 *Foto di referti* (esami del sangue, ecografie, EGDS, "
        "colonscopie, lettere di dimissione, prescrizioni, foto di confezioni "
        "di farmaci)\n"
        "📷 *Foto di sintomi* (rash, gonfiore, feci, vomito, ecc.)\n"
        "📄 *PDF / documenti* di referti se li hai digitali\n"
        "📝 *Testo libero* — la tua storia, sintomi cronici, allergie, paure\n"
        "🎙️ *Vocali* — se ti viene più facile raccontare a voce\n\n"
        "Non serve nessun comando: parla e basta. Quando hai finito di "
        "caricare scrivimi *\"basta\"* o *\"ho finito\"* e ti faccio una "
        "sintesi del caso.\n\n"
        "Tutto finisce automaticamente nel vault Obsidian sul tuo computer "
        "con backup permanente.",
        parse_mode="Markdown",
    )


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_chat.id):
        await update.message.reply_text("❌ Bot privato.")
        log.warning("rejected text from chat_id=%s", update.effective_chat.id)
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    if _is_reset_request(text):
        clear_sid()
        log.info("session reset via natural language: %r", text)
        await update.message.reply_text(
            "🔄 Sessione conversazionale azzerata. La memoria clinica del vault "
            "e i file di memoria sono conservati: ricominciamo solo la chat."
        )
        return

    log.info("text: %r", text[:120])
    reply = await with_typing(update, call_claude(text))
    await reply_long(update, reply)


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_chat.id):
        return
    photo = update.message.photo[-1]
    caption = (update.message.caption or "").strip()
    f = await ctx.bot.get_file(photo.file_id)
    msg_dt = update.message.date or datetime.utcnow()
    ts = msg_dt.strftime("%Y%m%d_%H%M%S")
    filename = f"tg_{ts}_{photo.file_unique_id}.jpg"

    dest = attachment_dir(msg_dt) / filename
    await f.download_to_drive(custom_path=str(dest))
    try:
        dest.chmod(0o600)
    except OSError:
        pass

    diary = append_attachment_to_diary(msg_dt, filename, "foto", caption)
    log.info("photo saved: %s | diary: %s (caption=%r)", dest, diary, caption[:80])

    prompt = (
        f"[Nuova foto archiviata nel vault: {dest}]\n"
        f"[Diario aggiornato con embed: {diary}]\n"
        f"Caption dell'utente: {caption or '(nessuna)'}\n\n"
        f"1) Leggi l'immagine con Read.\n"
        f"2) Analizzala come materiale clinico applicando il formato "
        f"strutturato della skill mydoctor.\n"
        f"3) Sostituisci nella nota di diario il blocco "
        f"'_(in attesa di valutazione)_' della voce appena aggiunta con la tua "
        f"valutazione strutturata (Procedura/Referto/Conclusioni/Quadro/"
        f"Domande per il medico/Bandiere rosse/In sintesi).\n"
        f"4) Se emergono dati clinici nuovi, aggiorna le note pertinenti del "
        f"vault (Conditions/, Differentials/, Visits/, Labs/, "
        f"Diagnostics pending/, Medications/, Prossima visita.md, Timeline.md, "
        f"00 Home.md) e i file di memoria.\n"
        f"5) Rispondi all'utente con la sintesi clinica (max ~3500 caratteri)."
    )
    reply = await with_typing(update, call_claude(prompt))
    await reply_long(update, reply)


async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_chat.id):
        return
    doc = update.message.document
    caption = (update.message.caption or "").strip()
    f = await ctx.bot.get_file(doc.file_id)
    msg_dt = update.message.date or datetime.utcnow()
    ts = msg_dt.strftime("%Y%m%d_%H%M%S")
    safe_name = (doc.file_name or f"doc_{doc.file_unique_id}").replace("/", "_")
    filename = f"tg_{ts}_{safe_name}"

    dest = attachment_dir(msg_dt) / filename
    await f.download_to_drive(custom_path=str(dest))
    try:
        dest.chmod(0o600)
    except OSError:
        pass

    diary = append_attachment_to_diary(msg_dt, filename, "documento", caption)
    log.info("document saved: %s | diary: %s (caption=%r)", dest, diary, caption[:80])

    prompt = (
        f"[Nuovo documento archiviato nel vault: {dest}]\n"
        f"[Diario aggiornato con link: {diary}]\n"
        f"Caption dell'utente: {caption or '(nessuna)'}\n\n"
        f"1) Leggi il documento con Read.\n"
        f"2) Analizzalo come materiale clinico (referto, esame, prescrizione, "
        f"lettera di dimissione, ecc.) applicando il formato strutturato della "
        f"skill mydoctor.\n"
        f"3) Se è un referto strutturato (analisi di laboratorio, EGDS, "
        f"colonscopia, ecografia, istologia, visita specialistica), CREA una "
        f"nuova nota dedicata nel vault nella cartella appropriata (Visits/ "
        f"per visite/procedure, Labs/ per laboratorio, Diagnostics pending/ "
        f"per esiti attesi appena ricevuti) usando i template di "
        f"vault/Templates/. Il filename segue 'YYYY-MM-DD nome_struttura.md'.\n"
        f"4) Aggiungi il link a questa nuova nota nel diario del giorno e nel "
        f"file Timeline.md.\n"
        f"5) Aggiorna le note pertinenti del vault (Conditions/, Differentials/, "
        f"Prossima visita.md, 00 Home.md) e i file di memoria.\n"
        f"6) Rispondi all'utente con la sintesi clinica (max ~3500 caratteri)."
    )
    reply = await with_typing(update, call_claude(prompt))
    await reply_long(update, reply)


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update.effective_chat.id):
        return

    voice = update.message.voice or update.message.audio
    if voice is None:
        return
    caption = (update.message.caption or "").strip()

    f = await ctx.bot.get_file(voice.file_id)
    msg_dt = update.message.date or datetime.utcnow()
    ts = msg_dt.strftime("%Y%m%d_%H%M%S")
    ext = Path(voice.file_path or "voice.ogg").suffix or ".ogg"
    filename = f"tg_{ts}_{voice.file_unique_id}{ext}"

    dest = attachment_dir(msg_dt) / filename
    await f.download_to_drive(custom_path=str(dest))
    try:
        dest.chmod(0o600)
    except OSError:
        pass

    diary = append_attachment_to_diary(msg_dt, filename, "vocale", caption)
    log.info("voice saved: %s | diary: %s", dest, diary)

    typing_done = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(update.effective_chat, typing_done))
    transcript = await asyncio.to_thread(_try_transcribe, dest)
    typing_done.set()
    try:
        await asyncio.wait_for(typing_task, timeout=2)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass

    if transcript:
        log.info("transcribed %d chars from %s", len(transcript), dest.name)
        prompt = (
            f"[Vocale Telegram salvato in {dest}, trascritto automaticamente]\n"
            f"Caption: {caption or '(nessuna)'}\n\n"
            f"Trascrizione:\n\"{transcript}\"\n\n"
            f"Aggiorna la nota di diario {diary} sostituendo "
            f"'_(in attesa di valutazione)_' con la trascrizione + valutazione "
            f"clinica strutturata. Aggiorna le note pertinenti del vault e i "
            f"file di memoria."
        )
    else:
        log.info("no transcription tool available — saving raw audio only")
        prompt = (
            f"[Vocale Telegram salvato in {dest}, NESSUNA TRASCRIZIONE "
            f"disponibile (faster-whisper non installato nel venv)]\n"
            f"Caption: {caption or '(nessuna)'}\n\n"
            f"Comunica all'utente: il vocale è archiviato nel vault, ma il bot "
            f"non ha una libreria di trascrizione installata. Suggerisci di "
            f"riassumere il contenuto in un messaggio testuale, oppure di "
            f"installare faster-whisper con `pip install faster-whisper` "
            f"(~150 MB, richiede ffmpeg). Aggiorna comunque la voce nel diario."
        )

    reply = await with_typing(update, call_claude(prompt))
    await reply_long(update, reply)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    if not TOKEN:
        log.error("MYDOCTOR_BOT_TOKEN non impostato in %s/.env", MYDOCTOR_HOME)
        sys.exit(2)
    if OWNER == 0:
        log.warning(
            "MYDOCTOR_OWNER_CHAT_ID non impostato — modalità DISCOVERY: "
            "scrivi al bot da Telegram con /start, copia il chat_id che ti "
            "dice, mettilo in .env, riavvia."
        )

    app = Application.builder().token(TOKEN).build()

    # Solo /start — Telegram lo invia automaticamente al primo contatto.
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, handle_voice)
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info(
        "MyDoctor bot starting (owner=%s, home=%s, vault=%s, claude=%s)",
        OWNER or "UNSET", MYDOCTOR_HOME, VAULT, CLAUDE_BIN,
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
