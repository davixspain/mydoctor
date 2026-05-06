# 🛠️ Setup — guida passo-passo

Questa guida copre l'installazione di MyDoctor su **Linux**, **macOS** e
**Windows**. La via più rapida è il wizard (`python3 install.py`), che gestisce
quasi tutto in automatico. Se preferisci capire cosa succede passo-passo o
hai una configurazione non standard, segui le sezioni sotto.

---

## 1. Prerequisiti

Prima di lanciare il wizard verifica di avere:

### Python 3.10 o superiore

```bash
# Linux/macOS
python3 --version

# Windows (PowerShell)
python --version
```

Se la versione è troppo vecchia o non installata:

- **Linux**: `sudo apt install python3 python3-venv` (Debian/Ubuntu) o
  `sudo dnf install python3` (Fedora) o `sudo pacman -S python` (Arch).
- **macOS**: installalo da [python.org/downloads](https://python.org/downloads)
  o via Homebrew: `brew install python@3.12`.
- **Windows**: download da [python.org](https://python.org/downloads), durante
  l'installazione **spunta "Add Python to PATH"**.

### Claude Code CLI

MyDoctor delega tutto il ragionamento clinico al CLI ufficiale Anthropic.
Devi averlo installato e autenticato.

- **Linux/macOS**:
  ```bash
  curl -fsSL https://claude.com/install.sh | bash
  claude login
  ```
- **Windows**: vedi
  [docs.anthropic.com/claude-code](https://docs.anthropic.com/en/docs/claude-code/install).

Verifica:
```bash
claude --version
```

### Obsidian (gratuito)

Scarica da [obsidian.md](https://obsidian.md). Disponibile per Win/Mac/Linux.
Non è strettamente obbligatorio (il vault è solo file markdown leggibili con
qualunque editor), ma è il modo migliore per esplorare il caso visualmente.

### Bot Telegram

Crei il bot con **@BotFather** su Telegram. È gratuito e richiede 2 minuti.
Il wizard ti guida automaticamente.

### Opzionale: ffmpeg + faster-whisper (per i vocali)

Se vuoi che i messaggi vocali Telegram vengano **trascritti automaticamente**
in locale:

- **Linux/macOS**: `sudo apt install ffmpeg` o `brew install ffmpeg`
- **Windows**: scarica `ffmpeg` da
  [ffmpeg.org](https://ffmpeg.org/download.html), aggiungi al PATH

Poi, dopo aver fatto l'installazione di MyDoctor:
```bash
~/MyDoctor/venv/bin/pip install faster-whisper
```

(Su Windows: `%USERPROFILE%\MyDoctor\venv\Scripts\pip install faster-whisper`)

I vocali funzionano comunque senza trascrizione: il file viene archiviato e
il bot ti chiede di riassumerlo per iscritto.

---

## 2. Installazione automatica (raccomandata)

Apri un terminale nella cartella dove hai estratto lo ZIP di MyDoctor:

```bash
cd MyDoctor-1.0.0/
python3 install.py
```

Il wizard fa **8 step**:

1. **Verifica prerequisiti** — controlla Python, Claude Code, ffmpeg, Obsidian
2. **Setup Telegram** — apre @BotFather nel browser, raccoglie il token, ti
   chiede di mandare `/start` al bot e rileva automaticamente il tuo chat_id
3. **Paths** — propone `$HOME/MyDoctor` (o `%USERPROFILE%\MyDoctor` su Win),
   accetti o cambi
4. **Copia template** — vault Obsidian + codice sorgente nella tua home
5. **Scrive `.env`** — config locale con permessi `600`
6. **Crea venv + installa dipendenze** Python
7. **Installa skill Claude + servizi schedulati** nativi del tuo OS:
   - Linux: `~/.config/systemd/user/mydoctor*.{service,timer}`
   - macOS: `~/Library/LaunchAgents/com.mydoctor.*.plist`
   - Windows: `schtasks` con tre task pianificati
8. **Test + apertura Obsidian** — manda un messaggio di benvenuto su Telegram
   e apre Obsidian sul vault appena creato

Tempo totale: **5–10 minuti**.

---

## 3. Installazione manuale (per chi vuole capire)

Se preferisci fare tutto a mano (es. server senza GUI, configurazioni
non-standard, audit di sicurezza):

### 3.1 Crea la directory di lavoro

```bash
mkdir -p ~/MyDoctor/{src,vault,logs}
cd ~/MyDoctor
```

### 3.2 Copia i file dal pacchetto

```bash
cp -r /path/to/MyDoctor-1.0.0/src/* ~/MyDoctor/src/
cp -r /path/to/MyDoctor-1.0.0/vault-template/* ~/MyDoctor/vault/
cp /path/to/MyDoctor-1.0.0/requirements.txt ~/MyDoctor/
```

(Su Windows usa `xcopy` o copia con Esplora risorse.)

### 3.3 Crea il `.env`

```bash
cp /path/to/MyDoctor-1.0.0/.env.example ~/MyDoctor/.env
chmod 600 ~/MyDoctor/.env
```

Apri `~/MyDoctor/.env` e compila:

```ini
MYDOCTOR_BOT_TOKEN=8123456789:AAH...    # da @BotFather
MYDOCTOR_OWNER_CHAT_ID=123456789        # il tuo chat_id Telegram
MYDOCTOR_HOME=/home/youruser/MyDoctor   # o C:\Users\You\MyDoctor su Windows
CLAUDE_BIN=                              # opzionale, lasciato vuoto cerca nel PATH
MYDOCTOR_TIMEOUT=480
MYDOCTOR_REVIEW_TIMEOUT=900
MYDOCTOR_DISABLE_PROACTIVE_PUSH=0
```

Per ottenere il tuo `chat_id`:
1. Crea il bot con @BotFather
2. Lancia il bot (vedi 3.5)
3. Manda `/start` da Telegram al tuo bot
4. Il bot ti scrive il chat_id (e poi ti rifiuta finché non lo aggiungi al `.env`)
5. Aggiungi il chat_id al `.env`, riavvia

### 3.4 Crea venv + installa dipendenze

```bash
cd ~/MyDoctor
python3 -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
```

Su Windows (PowerShell):
```powershell
cd $env:USERPROFILE\MyDoctor
python -m venv venv
.\venv\Scripts\pip install -U pip
.\venv\Scripts\pip install -r requirements.txt
```

### 3.5 Installa la skill Claude

```bash
mkdir -p ~/.claude/skills
cp -r /path/to/MyDoctor-1.0.0/skill/mydoctor ~/.claude/skills/
```

(Su Windows: `%USERPROFILE%\.claude\skills\mydoctor\SKILL.md`)

### 3.6 Test del bot in foreground

```bash
cd ~/MyDoctor
./venv/bin/python src/bot.py
```

Manda `/start` al tuo bot da Telegram. Se l'onboarding parte → tutto OK.
`Ctrl+C` per chiudere.

### 3.7 Installa il servizio (per avvio automatico)

#### Linux — systemd user units

Crea `~/.config/systemd/user/mydoctor.service`:

```ini
[Unit]
Description=MyDoctor — bot Telegram privato
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/USER/MyDoctor
EnvironmentFile=/home/USER/MyDoctor/.env
ExecStart=/home/USER/MyDoctor/venv/bin/python /home/USER/MyDoctor/src/bot.py
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/USER/MyDoctor/logs/mydoctor.stdout.log
StandardError=append:/home/USER/MyDoctor/logs/mydoctor.stderr.log
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
```

Sostituisci `/home/USER` col tuo path reale, poi:

```bash
systemctl --user daemon-reload
systemctl --user enable --now mydoctor.service
systemctl --user status mydoctor
```

Ripeti il pattern per i timer settimanale/mensile (vedi `services/linux/`
nel pacchetto).

#### macOS — launchd

Crea `~/Library/LaunchAgents/com.mydoctor.bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.mydoctor.bot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/USER/MyDoctor/venv/bin/python</string>
    <string>/Users/USER/MyDoctor/src/bot.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/USER/MyDoctor</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/USER/MyDoctor/logs/mydoctor.stdout.log</string>
  <key>StandardErrorPath</key><string>/Users/USER/MyDoctor/logs/mydoctor.stderr.log</string>
</dict>
</plist>
```

Sostituisci `USER`, poi:

```bash
launchctl load ~/Library/LaunchAgents/com.mydoctor.bot.plist
launchctl list | grep mydoctor
```

#### Windows — Task Scheduler

```powershell
$home = "$env:USERPROFILE\MyDoctor"
schtasks /Create /F /TN MyDoctorBot `
  /TR "`"$home\venv\Scripts\python.exe`" `"$home\src\bot.py`"" `
  /SC ONLOGON
```

Per i timer settimanale/mensile:

```powershell
schtasks /Create /F /TN MyDoctorWeekly `
  /TR "`"$home\venv\Scripts\python.exe`" `"$home\src\proactive_review.py`" --mode weekly" `
  /SC WEEKLY /D SUN /ST 20:00

schtasks /Create /F /TN MyDoctorMonthly `
  /TR "`"$home\venv\Scripts\python.exe`" `"$home\src\proactive_review.py`" --mode monthly" `
  /SC MONTHLY /D 1 /ST 20:00
```

---

## 4. Verifica post-installazione

Dopo l'installazione (automatica o manuale):

### Linux
```bash
systemctl --user is-active mydoctor                # active
systemctl --user list-timers | grep mydoctor       # 2 timer schedulati
tail -f ~/MyDoctor/logs/mydoctor.log               # log in tempo reale
```

### macOS
```bash
launchctl list | grep mydoctor    # 3 entries (bot, weekly, monthly)
tail -f ~/MyDoctor/logs/mydoctor.stdout.log
```

### Windows
```powershell
schtasks /Query /TN MyDoctorBot
Get-Content $env:USERPROFILE\MyDoctor\logs\mydoctor.stdout.log -Wait
```

### Test funzionale
1. Apri Telegram → cerca il tuo bot → manda `/start`
2. Dovresti ricevere il messaggio di benvenuto onboarding
3. Manda una foto qualunque → il bot la salva nel vault e risponde

---

## 5. Aggiornare MyDoctor

Quando arriva una nuova versione (vedi [`CHANGELOG.md`](../CHANGELOG.md)):

1. Scarica il nuovo ZIP
2. Estrai in una cartella temporanea
3. Sostituisci i file in `src/` e `skill/mydoctor/SKILL.md`:
   ```bash
   cp -r MyDoctor-1.1.0/src/* ~/MyDoctor/src/
   cp MyDoctor-1.1.0/skill/mydoctor/SKILL.md ~/.claude/skills/mydoctor/
   ```
4. Riavvia il servizio:
   ```bash
   systemctl --user restart mydoctor    # Linux
   launchctl unload ~/Library/LaunchAgents/com.mydoctor.bot.plist    # macOS
   launchctl load ~/Library/LaunchAgents/com.mydoctor.bot.plist
   schtasks /End /TN MyDoctorBot && schtasks /Run /TN MyDoctorBot    # Windows
   ```

**Il vault non viene mai toccato dagli aggiornamenti** — i tuoi dati restano
intatti.

---

## 6. Disinstallare

```bash
# Linux
systemctl --user disable --now mydoctor mydoctor-weekly.timer mydoctor-monthly.timer
rm ~/.config/systemd/user/mydoctor*.{service,timer}
systemctl --user daemon-reload

# macOS
launchctl unload ~/Library/LaunchAgents/com.mydoctor.*.plist
rm ~/Library/LaunchAgents/com.mydoctor.*.plist

# Windows
schtasks /Delete /TN MyDoctorBot /F
schtasks /Delete /TN MyDoctorWeekly /F
schtasks /Delete /TN MyDoctorMonthly /F
```

Per cancellare anche dati e config:

```bash
rm -rf ~/MyDoctor
rm -rf ~/.claude/skills/mydoctor
```

⚠️ Questo cancella **tutto il vault clinico**. Fai un backup prima
(`tar czf vault-backup.tar.gz ~/MyDoctor/vault/`).

---

## Problemi durante l'installazione?

Vedi [TROUBLESHOOTING.md](TROUBLESHOOTING.md) per i casi comuni, oppure
contatta il supporto (clienti **Pro**) entro 14 giorni dall'acquisto per il
rimborso.
