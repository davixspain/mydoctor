# 🔧 Troubleshooting — quando qualcosa non va

Casi comuni e come risolverli. Cerca per sintomo (Ctrl+F).

---

## Il bot non risponde su Telegram

### Diagnostica

```bash
# Linux
systemctl --user status mydoctor

# macOS
launchctl list | grep com.mydoctor.bot

# Windows
schtasks /Query /TN MyDoctorBot
```

### Cause comuni

#### 1. Il servizio non è attivo

**Linux**:
```bash
systemctl --user start mydoctor
systemctl --user status mydoctor
```

**macOS**:
```bash
launchctl load ~/Library/LaunchAgents/com.mydoctor.bot.plist
```

**Windows**:
```powershell
schtasks /Run /TN MyDoctorBot
```

#### 2. Token Telegram non valido / revocato

```bash
# Verifica che il token funzioni
source ~/MyDoctor/.env
curl "https://api.telegram.org/bot${MYDOCTOR_BOT_TOKEN}/getMe"
```

Se `ok: false` → vai su @BotFather → `/mybots` → seleziona il tuo bot →
`API Token` → copia il token, aggiornalo in `~/MyDoctor/.env`, riavvia.

#### 3. Chat ID non configurato

Cerca nel log: `rejected access from chat_id=...`. Significa che il bot
sta vedendo i messaggi ma non sa che sei tu il proprietario.

```bash
# Aggiorna ~/MyDoctor/.env
MYDOCTOR_OWNER_CHAT_ID=<il tuo chat_id>
```

#### 4. Internet bloccato / firewall

Verifica:
```bash
curl -sS https://api.telegram.org
```

Se risponde con HTML → connessione OK. Altrimenti controlla VPN/proxy/firewall.

---

## Errore: "claude binary missing"

Il bot non trova il CLI Claude Code.

### Soluzione 1 — verifica che claude sia installato

```bash
which claude
claude --version
```

Se non trovato → installa da [claude.com/claude-code](https://claude.com/claude-code).

### Soluzione 2 — imposta `CLAUDE_BIN` nel `.env`

```ini
CLAUDE_BIN=/home/youruser/.local/bin/claude   # Linux/macOS
# oppure
CLAUDE_BIN=C:\Users\You\.local\bin\claude.exe  # Windows
```

Riavvia il servizio.

### Soluzione 3 — autenticazione Claude scaduta

```bash
claude login
```

---

## "Claude exit non-zero"

Il subprocess di Claude è uscito con errore.

Controlla `~/MyDoctor/logs/mydoctor.log`:

```bash
tail -100 ~/MyDoctor/logs/mydoctor.log | grep -A2 "claude exit"
```

Cause comuni:
- **Quota API esaurita** → il messaggio Anthropic dirà `rate limit`
- **Authentication scaduta** → `claude login` di nuovo
- **Timeout** (>8 min) → richiesta troppo complessa, prova a spezzarla
- **Skill non installata** → `cp -r skill/mydoctor ~/.claude/skills/`

---

## Le foto non vengono archiviate

Verifica permessi del vault:

```bash
ls -ld ~/MyDoctor/vault ~/MyDoctor/vault/Attachments
# Devono essere accessibili in scrittura dal tuo utente
```

Se i permessi sono sbagliati:

```bash
chmod -R u+rw ~/MyDoctor/vault
```

**macOS**: il servizio launchd potrebbe essere in sandbox restrittivo.
Vedi `~/MyDoctor/logs/mydoctor.stderr.log` per errori specifici.

---

## I vocali non vengono trascritti

È normale! La trascrizione automatica è **opt-in**. Il vocale viene comunque
archiviato e il bot ti chiede di riassumerlo.

Per abilitare la trascrizione:

```bash
# Installa ffmpeg
sudo apt install ffmpeg          # Linux Debian/Ubuntu
brew install ffmpeg              # macOS
# Windows: scarica da ffmpeg.org

# Installa faster-whisper nel venv di MyDoctor
~/MyDoctor/venv/bin/pip install faster-whisper
```

(Su Windows: `%USERPROFILE%\MyDoctor\venv\Scripts\pip install faster-whisper`)

Primo uso: scarica ~150 MB di modelli (rallenta il primo vocale).

---

## La review settimanale non parte

### Verifica timer schedulato

**Linux**:
```bash
systemctl --user list-timers | grep mydoctor
# NEXT mostra quando partirà la prossima volta
```

**macOS**:
```bash
launchctl print gui/$(id -u)/com.mydoctor.weekly
# Cerca StartCalendarInterval
```

**Windows**:
```powershell
schtasks /Query /TN MyDoctorWeekly /V /FO LIST
```

### Test manuale

Lancia la review manualmente in dry-run:

```bash
cd ~/MyDoctor
./venv/bin/python src/proactive_review.py --mode weekly --dry-run
```

Se l'output è vuoto o errore → problema nella pipeline Claude. Vedi sezioni
sopra.

Se l'output mostra `[NIENTE_DI_RILEVANTE]` → la pipeline funziona, semplicemente
non c'era nulla di rilevante quella settimana.

---

## Obsidian non vede il vault

### Sintomo: Obsidian apre un altro vault o il dialog "Open vault"

Aggiungi il vault MyDoctor manualmente:
1. Apri Obsidian
2. Click sull'icona vault in basso a sinistra (o `Ctrl+P` → "Open another vault")
3. **Open folder as vault** → seleziona `~/MyDoctor/vault/`

### Sintomo: Obsidian apre il vault ma è vuoto

Verifica che il template sia stato copiato:
```bash
ls ~/MyDoctor/vault/
# Dovresti vedere: 00 Home.md, Profile.md, Timeline.md, ecc.
```

Se vuoto, lancia `python3 install.py` di nuovo per ricopiare il template.

---

## Dimenticato il chat_id, come lo recupero?

Su Telegram:
1. Apri la chat con il tuo bot
2. Cerca `@userinfobot` su Telegram → mandagli un messaggio
3. Ti risponde col tuo `id`

Oppure:
```bash
# Lancia il bot e guarda il log quando mandi un messaggio
tail -f ~/MyDoctor/logs/mydoctor.log
# Vedrai: "rejected access from chat_id=NNN" — quello è il tuo chat_id
```

Aggiungilo a `~/MyDoctor/.env` e riavvia.

---

## "Permission denied" durante l'install

### Linux/macOS

```bash
# Probabilmente stai cercando di scrivere in /opt o /usr — non serve
# L'installer mette tutto in $HOME, non richiede sudo
python3 install.py    # senza sudo
```

Se sei costretto a installare sotto `/opt` per policy aziendali, modifica
manualmente i path nel `.env`.

### Windows

Lancia PowerShell **come amministratore** se vedi errori `Access denied` nei
percorsi `%PROGRAMFILES%`. Per i percorsi `%USERPROFILE%` non serve admin.

---

## Il messaggio Telegram di benvenuto del wizard non arriva

Il wizard manda un test message dopo l'install. Se non lo vedi:

1. Controlla in @BotFather che il bot sia attivo
2. Verifica `~/MyDoctor/logs/mydoctor.log` per errori
3. Manda manualmente `/start` al bot — se risponde, è solo che il test del
   wizard è andato fuori sync

---

## Update da una versione precedente non parte

Verifica che hai sostituito **solo** i file in `src/` e in
`~/.claude/skills/mydoctor/`. **Non** sostituire:
- `~/MyDoctor/.env` (è il tuo config)
- `~/MyDoctor/vault/` (sono i tuoi dati)
- `~/MyDoctor/venv/` (può essere ricreato ma di solito non serve)

Riavvia dopo l'update:
```bash
systemctl --user restart mydoctor    # Linux
launchctl unload ... && launchctl load ...    # macOS
schtasks /End /TN MyDoctorBot && schtasks /Run /TN MyDoctorBot    # Windows
```

---

## Ho cancellato il vault per sbaglio

Se hai un backup → ripristinalo:
```bash
tar xzf vault-backup-2026-04-13.tar.gz -C ~/MyDoctor/
```

Se non hai backup → ricomincia con un vault vuoto:
```bash
cp -r /path/to/MyDoctor-1.0.0/vault-template ~/MyDoctor/vault
```

E imposta backup automatici **subito** (vedi [FAQ.md](FAQ.md) "Come faccio backup?").

---

## Rate limit Anthropic

Sintomo: messaggio del tipo `claude exit non-zero` con stderr che cita
`rate_limit_error` o `429`.

Soluzioni:
1. Aspetta qualche minuto (i rate limit hanno reset finestre)
2. Verifica il piano API Anthropic, considera upgrade se uso intenso
3. Disabilita temporaneamente il push proattivo:
   ```ini
   MYDOCTOR_DISABLE_PROACTIVE_PUSH=1
   ```

---

## Ancora bloccato?

1. **Cerca prima nel log**: `tail -200 ~/MyDoctor/logs/mydoctor.log` di solito
   contiene il messaggio specifico del problema.
2. **Controlla [FAQ.md](FAQ.md)** per la tua domanda.
3. **Cliente Pro**: scrivi al supporto. Non ti chiediamo di mandare il vault
   o dati sensibili — solo le righe di log specifiche del problema.
4. **Cliente Personal/Family**: la community + la documentazione.

Quando scrivi al supporto includi:
- Sistema operativo + versione
- Versione di MyDoctor (`cat VERSION`)
- Versione Python (`python3 --version`)
- Versione Claude (`claude --version`)
- Le ultime 50 righe rilevanti del log (anonimizza i dati clinici prima!)
- Cosa stavi facendo quando si è rotto
