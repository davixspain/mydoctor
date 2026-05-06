#!/usr/bin/env python3
"""MyDoctor — cross-platform installer wizard.

Lancia con:
    python3 install.py

Funziona su Linux, macOS, Windows con Python 3.10+. Guida l'utente attraverso:
    1. Detection del sistema operativo
    2. Check prerequisiti (Python, Claude Code, ffmpeg, Obsidian)
    3. Setup del bot Telegram (apre @BotFather nel browser)
    4. Configurazione dei paths
    5. Creazione dei venv Python e installazione dipendenze
    6. Clonazione del vault template nella home dell'utente
    7. Installazione skill Claude Code
    8. Installazione dei servizi schedulati (systemd / launchd / Task Scheduler)
    9. Test di connessione end-to-end
   10. Apertura di Obsidian sul vault appena creato

Nessuna dipendenza esterna (usa solo stdlib). Self-contained.
"""
from __future__ import annotations

import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────
PRODUCT_NAME = "MyDoctor"
VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).resolve().parent
MIN_PYTHON = (3, 10)


# ── Visual helpers ────────────────────────────────────────────────────────────
class Color:
    """ANSI codes — autodetect TTY support."""
    if sys.stdout.isatty() and platform.system() != "Windows":
        BOLD = "\033[1m"
        DIM = "\033[2m"
        OK = "\033[92m"
        WARN = "\033[93m"
        ERR = "\033[91m"
        INFO = "\033[94m"
        END = "\033[0m"
    else:
        BOLD = DIM = OK = WARN = ERR = INFO = END = ""


def banner() -> None:
    print(f"\n{Color.BOLD}🩺 {PRODUCT_NAME} — installer v{VERSION}{Color.END}")
    print(f"{Color.DIM}Personal AI doctor — cross-platform setup wizard{Color.END}\n")


def step(num: int, total: int, title: str) -> None:
    print(f"\n{Color.BOLD}[{num}/{total}] {title}{Color.END}")
    print(f"{Color.DIM}{'─' * (len(title) + 8)}{Color.END}")


def ok(msg: str) -> None:
    print(f"  {Color.OK}✓{Color.END} {msg}")


def warn(msg: str) -> None:
    print(f"  {Color.WARN}⚠{Color.END} {msg}")


def err(msg: str) -> None:
    print(f"  {Color.ERR}✗{Color.END} {msg}")


def info(msg: str) -> None:
    print(f"  {Color.INFO}→{Color.END} {msg}")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


def ask_yesno(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"  {prompt} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y") or answer.startswith("s")


def fatal(msg: str, code: int = 1) -> None:
    err(msg)
    print(f"\n{Color.ERR}Installazione interrotta.{Color.END}\n")
    sys.exit(code)


# ── OS detection ──────────────────────────────────────────────────────────────
def detect_os() -> str:
    sys_name = platform.system()
    if sys_name == "Linux":
        return "linux"
    if sys_name == "Darwin":
        return "macos"
    if sys_name == "Windows":
        return "windows"
    return sys_name.lower()


def default_home(os_type: str) -> Path:
    """Default install location, per OS convention."""
    if os_type == "windows":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "MyDoctor"
    return Path.home() / "MyDoctor"


# ── Prerequisite checks ───────────────────────────────────────────────────────
def check_python() -> bool:
    cur = sys.version_info[:2]
    if cur >= MIN_PYTHON:
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} OK")
        return True
    err(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ richiesto, trovato {cur[0]}.{cur[1]}")
    return False


def check_claude() -> Optional[Path]:
    found = shutil.which("claude")
    if found:
        ok(f"Claude Code CLI trovato in {found}")
        return Path(found)
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".local" / "bin" / "claude.exe",
        Path("/usr/local/bin/claude"),
    ]
    for c in candidates:
        if c.exists():
            ok(f"Claude Code CLI trovato in {c}")
            return c
    warn("Claude Code CLI non trovato nel PATH.")
    info("Installa da https://claude.com/claude-code prima di proseguire.")
    info("Su Linux/macOS:  curl -fsSL https://claude.com/install.sh | bash")
    info("Poi: claude login")
    return None


def check_ffmpeg() -> bool:
    if shutil.which("ffmpeg"):
        ok("ffmpeg trovato (vocali → trascrizione opzionale)")
        return True
    warn("ffmpeg non trovato (i vocali Telegram funzioneranno comunque, ma senza trascrizione locale).")
    info("Per abilitare la trascrizione installa ffmpeg + faster-whisper. Vedi docs/SETUP.md.")
    return False


def check_obsidian(os_type: str) -> bool:
    candidates = []
    if os_type == "linux":
        candidates = [Path("/usr/bin/obsidian"), Path("/snap/bin/obsidian"),
                      Path("/var/lib/flatpak/exports/bin/md.obsidian.Obsidian")]
    elif os_type == "macos":
        candidates = [Path("/Applications/Obsidian.app")]
    elif os_type == "windows":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian" / "Obsidian.exe",
            Path("C:/Program Files/Obsidian/Obsidian.exe"),
        ]
    for c in candidates:
        if c.exists():
            ok(f"Obsidian trovato in {c}")
            return True
    warn("Obsidian non trovato — scaricalo gratuito da https://obsidian.md")
    info("Il vault funzionerà comunque (è solo file markdown), ma Obsidian dà l'esperienza migliore.")
    return False


# ── Telegram setup ────────────────────────────────────────────────────────────
def telegram_setup() -> tuple[str, int]:
    print()
    info("Setup del bot Telegram. Se non hai ancora creato un bot:")
    info("  1. Apri @BotFather su Telegram (lo apriamo nel browser tra un attimo)")
    info("  2. Scrivi /newbot, scegli un nome (es. 'Mario Doctor') e uno username")
    info("     (es. @mario_mydoctor_bot — deve finire con '_bot' o 'Bot')")
    info("  3. BotFather ti darà un token tipo '8123456789:AAH...' — copialo")
    print()

    if ask_yesno("Apro @BotFather nel browser ora?", default=True):
        try:
            webbrowser.open("https://t.me/BotFather")
            ok("Browser aperto su @BotFather")
        except Exception:
            warn("Non riesco ad aprire il browser. Vai manualmente a: https://t.me/BotFather")

    print()
    while True:
        token = getpass.getpass("  Incolla il token del bot (input nascosto): ").strip()
        if re.fullmatch(r"\d{8,12}:[A-Za-z0-9_-]{30,}", token):
            ok("Formato token OK")
            break
        err("Formato token non valido. Deve essere tipo '8123456789:AAH...'")

    # Verifica il token via getMe
    info("Verifica del token con Telegram...")
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=15
        ) as resp:
            data = json.loads(resp.read().decode())
        if not data.get("ok"):
            fatal(f"Telegram ha rifiutato il token: {data.get('description', 'errore sconosciuto')}")
        bot_info = data["result"]
        username = bot_info.get("username", "?")
        ok(f"Bot Telegram OK: @{username} (id {bot_info['id']})")
    except urllib.error.URLError as exc:
        fatal(f"Errore di rete contattando Telegram: {exc}")

    print()
    info(f"Ora apri Telegram e cerca @{username} (o clicca: https://t.me/{username})")
    info("Manda /start al bot dal TUO account Telegram.")
    info("Tornerò a controllare il messaggio che arriva, mi serve il TUO chat_id.")
    print()

    if ask_yesno(f"Apro https://t.me/{username} nel browser?", default=True):
        try:
            webbrowser.open(f"https://t.me/{username}")
        except Exception:
            pass

    print()
    info("Sto ascoltando i messaggi in arrivo al bot — manda /start ora...")

    chat_id = _wait_for_chat_id(token)
    ok(f"Chat ID rilevato: {chat_id}")

    return token, chat_id


def _wait_for_chat_id(token: str, timeout_seconds: int = 180) -> int:
    """Polling getUpdates fino a ricevere un messaggio."""
    end_time = time.time() + timeout_seconds
    last_seen_offset = 0
    while time.time() < end_time:
        try:
            with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/getUpdates?offset={last_seen_offset}&timeout=10",
                timeout=15,
            ) as resp:
                data = json.loads(resp.read().decode())
            if data.get("ok") and data["result"]:
                for update in data["result"]:
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat = msg.get("chat", {})
                    if chat.get("id") and ("/start" in text or msg):
                        return int(chat["id"])
                    last_seen_offset = update["update_id"] + 1
        except urllib.error.URLError:
            time.sleep(2)
        except Exception:
            time.sleep(2)
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(1)
    print()
    manual = ask("Non sono riuscito a rilevare automaticamente. Inserisci il tuo chat_id manualmente")
    if not manual.isdigit():
        fatal("Chat ID non valido. Riavvia l'installer.")
    return int(manual)


# ── Filesystem setup ──────────────────────────────────────────────────────────
def setup_paths(os_type: str) -> Path:
    print()
    default = default_home(os_type)
    info(f"Default install location: {default}")
    custom = ask(f"Premi invio per accettare, o digita un path alternativo")
    home = Path(custom).expanduser().resolve() if custom else default
    home.mkdir(parents=True, exist_ok=True)
    ok(f"MYDOCTOR_HOME = {home}")
    return home


def copy_vault_template(home: Path) -> None:
    target = home / "vault"
    if target.exists() and any(target.iterdir()):
        if not ask_yesno(f"Il vault {target} esiste già e non è vuoto. Sovrascrivo?", default=False):
            ok("Vault esistente conservato.")
            return
    src = SCRIPT_DIR / "vault-template"
    if not src.exists():
        fatal(f"vault-template non trovato in {src}. Pacchetto corrotto?")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src, target)
    # Rimuovo i .gitkeep dalle copie utente — non servono nel vault attivo
    for keep in target.rglob(".gitkeep"):
        keep.unlink()
    ok(f"Vault template copiato in {target}")


def copy_source_files(home: Path) -> None:
    src_dir = home / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("bot.py", "proactive_review.py"):
        src = SCRIPT_DIR / "src" / fname
        if not src.exists():
            fatal(f"File sorgente mancante: {src}")
        shutil.copy2(src, src_dir / fname)
    ok(f"Codice sorgente copiato in {src_dir}")


def write_env_file(home: Path, token: str, chat_id: int, claude_bin: Optional[Path]) -> None:
    env_path = home / ".env"
    lines = [
        "# MyDoctor — config locale (generato dal wizard).",
        "# NON committare, NON condividere. Permessi 600.",
        "",
        f"MYDOCTOR_BOT_TOKEN={token}",
        f"MYDOCTOR_OWNER_CHAT_ID={chat_id}",
        f"MYDOCTOR_HOME={home}",
        f"CLAUDE_BIN={claude_bin or ''}",
        "",
        "# Tuning (defaults sicuri)",
        "MYDOCTOR_TIMEOUT=480",
        "MYDOCTOR_REVIEW_TIMEOUT=900",
        "MYDOCTOR_DISABLE_PROACTIVE_PUSH=0",
        "",
    ]
    env_path.write_text("\n".join(lines))
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    ok(f".env scritto in {env_path}")


def setup_venv(home: Path) -> Path:
    venv_dir = home / "venv"
    if venv_dir.exists():
        ok(f"venv esistente in {venv_dir} — riuso")
    else:
        info(f"Creo venv in {venv_dir} (può richiedere ~30s)...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        ok("venv creato")

    pip = venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "pip"
    info("Installo dipendenze (python-telegram-bot, dotenv)...")
    subprocess.run(
        [str(pip), "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(pip), "install", "--quiet", "-r", str(SCRIPT_DIR / "requirements.txt")],
        check=True,
    )
    ok("Dipendenze installate")
    return venv_dir


def install_claude_skill() -> None:
    skill_src = SCRIPT_DIR / "skill" / "mydoctor"
    if not skill_src.exists():
        warn("Skill source non trovata — salto installazione skill")
        return
    skill_dst = Path.home() / ".claude" / "skills" / "mydoctor"
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    if skill_dst.exists():
        if not ask_yesno(f"La skill è già installata in {skill_dst}. Sovrascrivo?", default=True):
            ok("Skill esistente conservata.")
            return
        shutil.rmtree(skill_dst)
    shutil.copytree(skill_src, skill_dst)
    ok(f"Skill installata in {skill_dst}")


# ── Service installation per OS ───────────────────────────────────────────────
def install_systemd(home: Path, venv: Path) -> None:
    """Linux: systemd user units."""
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    python = venv / "bin" / "python"
    units = [
        ("mydoctor.service", _systemd_bot_unit(home, python)),
        ("mydoctor-weekly.service", _systemd_review_unit(home, python, "weekly")),
        ("mydoctor-weekly.timer", _systemd_timer_unit("weekly", "Sun 20:00:00")),
        ("mydoctor-monthly.service", _systemd_review_unit(home, python, "monthly")),
        ("mydoctor-monthly.timer", _systemd_timer_unit("monthly", "*-*-01 20:00:00", randomized=300)),
    ]
    for name, content in units:
        (systemd_dir / name).write_text(content)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", "mydoctor.service"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now",
                    "mydoctor-weekly.timer", "mydoctor-monthly.timer"], check=False)
    ok(f"systemd units installati in {systemd_dir} e attivati")


def _systemd_bot_unit(home: Path, python: Path) -> str:
    return f"""[Unit]
Description=MyDoctor — bot Telegram privato
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={home}
EnvironmentFile={home}/.env
ExecStart={python} {home}/src/bot.py
Restart=on-failure
RestartSec=5
StandardOutput=append:{home}/logs/mydoctor.stdout.log
StandardError=append:{home}/logs/mydoctor.stderr.log

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths={home} %h/.claude

[Install]
WantedBy=default.target
"""


def _systemd_review_unit(home: Path, python: Path, mode: str) -> str:
    return f"""[Unit]
Description=MyDoctor — review proattivo {mode}
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={home}
EnvironmentFile={home}/.env
ExecStart={python} {home}/src/proactive_review.py --mode {mode}
StandardOutput=append:{home}/logs/review-{mode}.log
StandardError=append:{home}/logs/review-{mode}.log
TimeoutStartSec=20min

NoNewPrivileges=true
PrivateTmp=true
"""


def _systemd_timer_unit(mode: str, calendar: str, randomized: int = 120) -> str:
    return f"""[Unit]
Description=Trigger MyDoctor review {mode}

[Timer]
OnCalendar={calendar}
Persistent=true
RandomizedDelaySec={randomized}
Unit=mydoctor-{mode}.service

[Install]
WantedBy=timers.target
"""


def install_launchd(home: Path, venv: Path) -> None:
    """macOS: launchd plist."""
    launch_dir = Path.home() / "Library" / "LaunchAgents"
    launch_dir.mkdir(parents=True, exist_ok=True)
    python = venv / "bin" / "python"
    plists = [
        ("com.mydoctor.bot.plist", _launchd_bot_plist(home, python)),
        ("com.mydoctor.weekly.plist", _launchd_review_plist(home, python, "weekly", 0)),
        ("com.mydoctor.monthly.plist", _launchd_review_plist(home, python, "monthly", 1)),
    ]
    for name, content in plists:
        path = launch_dir / name
        path.write_text(content)
        try:
            subprocess.run(["launchctl", "unload", str(path)], capture_output=True, check=False)
        except Exception:
            pass
        subprocess.run(["launchctl", "load", str(path)], check=False)
    ok(f"launchd plists installati in {launch_dir}")


def _launchd_bot_plist(home: Path, python: Path) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.mydoctor.bot</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{home}/src/bot.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{home}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MYDOCTOR_HOME</key>
    <string>{home}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{home}/logs/mydoctor.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>{home}/logs/mydoctor.stderr.log</string>
</dict>
</plist>
"""


def _launchd_review_plist(home: Path, python: Path, mode: str, weekday_or_day: int) -> str:
    """weekly: Sunday 20:00 (Weekday=0). monthly: day 1 at 20:00 (Day=1)."""
    calendar_key = "Weekday" if mode == "weekly" else "Day"
    calendar_val = 0 if mode == "weekly" else 1
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.mydoctor.{mode}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{home}/src/proactive_review.py</string>
    <string>--mode</string>
    <string>{mode}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{home}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>{calendar_key}</key>
    <integer>{calendar_val}</integer>
    <key>Hour</key>
    <integer>20</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{home}/logs/review-{mode}.log</string>
  <key>StandardErrorPath</key>
  <string>{home}/logs/review-{mode}.log</string>
</dict>
</plist>
"""


def install_windows_tasks(home: Path, venv: Path) -> None:
    """Windows: Task Scheduler — uses schtasks.exe."""
    python = venv / "Scripts" / "python.exe"
    bot_cmd = f'"{python}" "{home}\\src\\bot.py"'
    weekly_cmd = f'"{python}" "{home}\\src\\proactive_review.py" --mode weekly'
    monthly_cmd = f'"{python}" "{home}\\src\\proactive_review.py" --mode monthly'

    tasks = [
        ("MyDoctorBot", bot_cmd, "ONLOGON", None, None),
        ("MyDoctorWeekly", weekly_cmd, "WEEKLY", "SUN", "20:00"),
        ("MyDoctorMonthly", monthly_cmd, "MONTHLY", "1", "20:00"),
    ]
    for name, cmd, schedule, day, time_ in tasks:
        args = ["schtasks", "/Create", "/F", "/TN", name, "/TR", cmd, "/SC", schedule]
        if day:
            args += (["/D", day] if schedule == "WEEKLY" else ["/D", day])
        if time_:
            args += ["/ST", time_]
        try:
            subprocess.run(args, check=True, capture_output=True)
            ok(f"Task '{name}' creato ({schedule})")
        except subprocess.CalledProcessError as exc:
            warn(f"Errore creando task {name}: {exc.stderr.decode(errors='replace')[:200]}")


def test_telegram(token: str, chat_id: int) -> None:
    """Manda un messaggio di benvenuto al chat_id owner."""
    info("Invio un messaggio di test al tuo Telegram...")
    text = (
        f"✅ Installazione MyDoctor v{VERSION} completata!\n\n"
        "Manda /start al bot per iniziare l'onboarding del tuo caso clinico."
    )
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if data.get("ok"):
            ok("Messaggio di test inviato — controlla Telegram!")
        else:
            warn(f"Telegram ha risposto: {data}")
    except urllib.error.URLError as exc:
        warn(f"Test Telegram fallito (rete): {exc}")


def open_obsidian(home: Path, os_type: str) -> None:
    vault = home / "vault"
    if not vault.exists():
        return
    if not ask_yesno(f"Apro Obsidian sul vault {vault}?", default=True):
        return
    obsidian_uri = f"obsidian://open?path={urllib.parse.quote(str(vault))}"
    try:
        if os_type == "linux":
            subprocess.Popen(["xdg-open", obsidian_uri], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        elif os_type == "macos":
            subprocess.Popen(["open", obsidian_uri])
        elif os_type == "windows":
            os.startfile(obsidian_uri)  # type: ignore[attr-defined]
        ok("Obsidian aperto sul vault")
    except Exception as exc:
        warn(f"Non riesco ad aprire Obsidian automaticamente: {exc}")
        info(f"Apri Obsidian manualmente e seleziona la cartella: {vault}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    banner()

    if not check_python():
        fatal("Aggiorna Python a 3.10 o superiore e riprova.")

    os_type = detect_os()
    print(f"  {Color.INFO}→{Color.END} Sistema operativo rilevato: {Color.BOLD}{os_type}{Color.END}")
    if not ask_yesno("È corretto?", default=True):
        fatal("Interrompi e contatta il supporto se l'auto-detect è sbagliato.")

    if os_type not in ("linux", "macos", "windows"):
        fatal(f"OS '{os_type}' non supportato. Vedi docs/SETUP.md per workaround.")

    # ── Step 1: Prerequisiti ──
    step(1, 8, "Verifica prerequisiti")
    claude_bin = check_claude()
    if claude_bin is None:
        if not ask_yesno("Continuo senza Claude Code (lo installerai dopo)?", default=False):
            fatal("Installa Claude Code e riavvia il wizard.")
    check_ffmpeg()
    check_obsidian(os_type)

    # ── Step 2: Telegram ──
    step(2, 8, "Setup bot Telegram")
    token, chat_id = telegram_setup()

    # ── Step 3: Paths ──
    step(3, 8, "Configurazione paths")
    home = setup_paths(os_type)

    # ── Step 4: Vault + sources ──
    step(4, 8, "Copia vault template e codice sorgente")
    copy_vault_template(home)
    copy_source_files(home)
    (home / "logs").mkdir(exist_ok=True)

    # ── Step 5: .env ──
    step(5, 8, "Scrittura .env")
    write_env_file(home, token, chat_id, claude_bin)

    # ── Step 6: venv + deps ──
    step(6, 8, "Virtual environment e dipendenze Python")
    venv = setup_venv(home)

    # ── Step 7: Skill + servizi ──
    step(7, 8, "Installazione skill Claude e servizi schedulati")
    install_claude_skill()
    if os_type == "linux":
        install_systemd(home, venv)
    elif os_type == "macos":
        install_launchd(home, venv)
    elif os_type == "windows":
        install_windows_tasks(home, venv)

    # ── Step 8: Test + Obsidian ──
    step(8, 8, "Test e apertura Obsidian")
    test_telegram(token, chat_id)
    open_obsidian(home, os_type)

    # ── Done ──
    print(f"\n{Color.OK}{Color.BOLD}🎉 Installazione completata!{Color.END}\n")
    print(f"  Vault: {Color.BOLD}{home}/vault/{Color.END}")
    print(f"  Logs: {home}/logs/")
    print(f"  Config: {home}/.env (chmod 600)")
    print()
    print(f"  {Color.INFO}Prossimo passo:{Color.END} apri Telegram e manda {Color.BOLD}/start{Color.END} al tuo bot.")
    print(f"  Documentazione: {SCRIPT_DIR}/docs/")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Color.WARN}Installazione interrotta dall'utente.{Color.END}\n")
        sys.exit(130)
