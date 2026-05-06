# 🏗️ Architettura — come funziona MyDoctor

Doc tecnica per chi vuole capire cosa succede sotto il cofano. Leggila se sei
ingegnere e vuoi auditare il prodotto, oppure se sei curioso e ti piace il
"dietro le quinte".

---

## Schema di alto livello

```
                 ┌──────────────────────┐
                 │   Telegram client    │
                 │  (iOS/Android/Web/   │
                 │   Desktop/qualsiasi) │
                 └─────────┬────────────┘
                           │ HTTPS (Telegram Bot API)
                           ▼
              ┌────────────────────────┐
              │   bot.py (long poll)   │
              │   Python 3.10+ in venv │
              └─────────┬──────────────┘
                        │ subprocess
                        ▼
              ┌────────────────────────┐
              │  Claude Code CLI       │
              │  (--session-id)        │
              │  Skill `mydoctor`      │
              └─────────┬──────────────┘
                        │ Read/Write/Edit tools
                        ▼
              ┌────────────────────────┐
              │  Vault Obsidian        │ ◄────  Obsidian.app (lettura
              │  /home/u/MyDoctor/vault│        + edit manuale)
              │  • Visits/             │
              │  • Labs/               │
              │  • Conditions/         │
              │  • Differentials/      │
              │  • Symptom diary/      │
              │  • Medications/        │
              │  • Doctors/            │
              │  • Diagnostics pending/│
              │  • Templates/          │
              │  • Attachments/<date>/ │
              └────────────────────────┘

   ▲                                                ▲
   │                                                │
   │  systemd / launchd / Task Scheduler            │
   │  ─────────────────────────────────             │
   │  • mydoctor.service (bot, sempre attivo)       │
   │  • mydoctor-weekly  (Sun 20:00, push se serve) │
   │  • mydoctor-monthly (1st 20:00, push se serve) │
```

---

## Componenti

### 1. `src/bot.py` — interfaccia Telegram

**Tecnologia**: `python-telegram-bot 22+` in long polling.

**Flow per un messaggio in arrivo**:
1. Telegram POSTa l'update (testo, foto, documento, vocale).
2. `bot.py` filtra: solo `chat_id == OWNER` viene processato. Altri rifiutati.
3. Se è una **foto** → scaricata in
   `vault/Attachments/YYYY-MM-DD/tg_<ts>_<id>.jpg`. Aggiornato il diario del
   giorno con un blocco
   ```markdown
   ### HH:MM — foto ricevuta via Telegram
   ![[../Attachments/YYYY-MM-DD/tg_<ts>_<id>.jpg]]
   _(in attesa di valutazione)_
   ```
4. Se è un **documento** (PDF, ecc.) → idem in Attachments + entry in diario.
5. Se è un **vocale** → archiviato. Tentata trascrizione locale con
   `faster-whisper` (se installato), `openai-whisper` (fallback), o `whisper`
   CLI. Se nulla disponibile → archivio + nota all'utente.
6. **Subprocess `claude`** lanciato con `--resume <session_id>` (o
   `--session-id` la prima volta), `--dangerously-skip-permissions`, e prompt
   completo: PRIMER + onboarding-prefix + payload-specifico.
7. Output di Claude → spedito via `sendMessage` Telegram, chunked a 4000
   caratteri max.

**Stato persistente**:
- `~/.session_id` — UUID della sessione Claude corrente. Permette continuità
  conversazionale tra messaggi.
- `~/.onboarding` — flag file che attiva la modalità onboarding.

### 2. Skill `mydoctor` — il "cervello clinico"

**File**: `~/.claude/skills/mydoctor/SKILL.md`

Descrive a Claude:
- Hard rules (lingua italiana, leggi `Profile.md`, distingui ospedali, etc.)
- Output structure obbligatorio (Procedura → Referto → Conclusioni → Quadro
  → Domande → Bandiere rosse → In sintesi)
- Workflow di aggiornamento di vault e memoria
- Convenzioni di filename, frontmatter, wikilink

Claude carica la skill **automaticamente** quando vede contenuto medicale
nella working directory `MYDOCTOR_HOME` o nel prompt.

### 3. Vault Obsidian — la "cartella clinica"

**Filesystem**: `~/MyDoctor/vault/`

Tutto è **markdown puro** con frontmatter YAML. Niente database, niente
binari. Puoi aprirlo con Obsidian, VS Code, vim, qualsiasi editor di testo.

**Convenzioni**:
- Filename `YYYY-MM-DD <descrizione>.md` per visite/labs ordinati
  cronologicamente per nome
- Wikilink Obsidian `[[Folder/File|Display]]` per cross-reference
- Tag standard `#visita #esame #sintomo #farmaco #allergia #differenziale`
- Frontmatter con campi tipizzati (`type`, `date`, `status`, ecc.)

**Backup naturale**: `git init && git add . && git commit -m "v1"`. Versioning
free + storage minimo (markdown comprime bene).

### 4. `src/proactive_review.py` — agent proattivo

**Quando**: schedulato dal sistema operativo (systemd timer / launchd /
Task Scheduler).

**Flow**:
1. Costruisce prompt strutturato (`weekly` o `monthly`) che chiede a Claude
   di leggere il diario degli ultimi N giorni.
2. Fresh session UUID (non si confonde con la chat live).
3. Subprocess `claude -p ...` con timeout (default 15 min).
4. Parsing output:
   - Se contiene `[NIENTE_DI_RILEVANTE]` → log + exit. Nessuna interruzione.
   - Altrimenti → `sendMessage` HTTP diretto a Telegram (no dependency su
     `python-telegram-bot` per ridurre il payload del job).
5. Side-effect: Claude scrive sempre una nota
   `vault/Symptom diary/_review_settimanale_YYYY-MM-DD.md` (o `_review_mensile_`)
   come audit trail.

### 5. Schedulers OS-native

| OS | Tecnologia | File |
|---|---|---|
| Linux | `systemd --user` units | `~/.config/systemd/user/mydoctor*.{service,timer}` |
| macOS | `launchd` LaunchAgents | `~/Library/LaunchAgents/com.mydoctor.*.plist` |
| Windows | Task Scheduler | `schtasks` con 3 task (bot ONLOGON, review WEEKLY/MONTHLY) |

**Persistent=true** (Linux), o equivalenti, garantiscono che job persi (PC
spento all'orario schedulato) vengano recuperati al prossimo boot.

---

## Modello dati

### Memoria Claude — strato di lavoro

`~/.claude/projects/-<MYDOCTOR_HOME>/memory/`:
- `MEMORY.md` — index, sempre caricato in context
- `user_*.md` — profilo utente, allergie, preferenze
- `project_*.md` — caso clinico in corso, differenziali aperti
- `feedback_*.md` — feedback sull'interazione (es. "rispondimi più conciso")
- `reference_*.md` — pointer a sistemi esterni (Obsidian, Linear, ecc.)

Carico in context all'avvio della sessione: ~2–5KB. Tagliato a 200 righe di
`MEMORY.md` per evitare bloat.

### Vault Obsidian — fonte di verità

```
vault/
├── 00 Home.md              dashboard, sempre il punto di partenza
├── Profile.md              anagrafica utente
├── Timeline.md             cronologia master
├── Red Flags.md            criteri PS/112
├── Prossima visita.md      briefing per il MMG
├── Visits/                 una nota per visita ospedaliera
├── Labs/                   una nota per sessione analisi
├── Conditions/             "storie cliniche" attive
├── Differentials/          ipotesi diagnostiche aperte
├── Medications/            farmaci e allergie
├── Diagnostics pending/    esami in coda
├── Doctors/                rubrica
├── Symptom diary/          1 nota per giorno
└── Attachments/YYYY-MM-DD/ foto/PDF binari
```

### Differenza vault vs memoria

| Vault | Memoria Claude |
|---|---|
| Permanente per anni | Strato di lavoro |
| Ricco di cross-link | Sintetico |
| Letto da Claude on-demand | Caricato sempre in context |
| Editabile dall'utente | Editabile da Claude |
| Versionabile con git | Non versionata |

In caso di conflitto: **vault wins**. Claude aggiorna la memoria di
conseguenza.

---

## Pattern detection — come funziona

### Real-time (su ogni messaggio)

Il PRIMER di `bot.py` istruisce Claude:

> Ogni volta che arriva un nuovo dato, PRIMA di rispondere all'utente:
> (a) lista i file in `vault/Symptom diary/` degli ultimi 60 giorni
> (b) leggi i 5–10 più recenti rilevanti
> (c) cerca correlazioni alimento→sintomo entro 6–24h con ≥2 ricorrenze
> (d) se trovi un pattern, **NOMINALO esplicitamente** nella risposta come
>     `📊 Pattern osservato:`

### Batch (review settimanale/mensile)

Il prompt schedulato chiede a Claude di confrontare:
- **Settimanale**: ultimi 7 giorni vs i 30 precedenti
- **Mensile**: ultimi 30 giorni vs i 90 precedenti (drift su orizzonte lungo)

Output: messaggio Telegram solo se rilevante. Altrimenti `[NIENTE_DI_RILEVANTE]`
e silence.

---

## Why these choices

**Perché filesystem (Obsidian) e non un database?**
- Markdown è eternamente leggibile (50 anni da oggi avrai ancora un editor
  che apre `.md`).
- Niente migration script da mantenere.
- Versionabile con git.
- L'utente può editare manualmente quando vuole, senza sapere SQL.
- Obsidian dà un'esperienza visuale gratis.

**Perché Claude Code CLI e non un wrapper diretto sull'API Anthropic?**
- Claude Code ha già `Read/Write/Edit/Glob/Grep/Bash` tools out of the box.
- La skill format è plug-and-play (drop di un `SKILL.md`).
- L'utente vede ogni operazione come tool call, possibilità di audit.
- Stessa CLI usata in produzione → stabilità.

**Perché Telegram e non WhatsApp/iMessage?**
- API Telegram bot è gratuita, illimitata, semplice.
- Bot privati molto più semplici da realizzare (no Meta Business approval).
- Cross-platform mobile gratis.
- Il bot accetta solo l'OWNER chat_id → privacy locked-down per default.

**Perché niente cloud / SaaS?**
- Dati clinici = dati sensibilissimi.
- L'utente vuole controllo totale.
- Niente subscription = vendita una tantum + buona unit economics.
- v2.0 mobile potrebbe introdurre cloud opzionale (vedi ROADMAP.md).

---

## Estendibilità

Il prodotto è progettato per essere **modificabile** dal compratore:

- Lingua italiana hardcoded? Cambia `SKILL.md` per inglese.
- Vuoi aggiungere una cartella `Imaging/` per RX/TC? Crei la directory + un
  template + una riga nella skill.
- Schedule diverso? Modifica `OnCalendar` nel `.timer` (Linux) o
  `StartCalendarInterval` (macOS).
- Push proattivo via email invece di Telegram? Modifica `send_telegram()`
  in `proactive_review.py` per usare SMTP.

Tutto il codice è **leggibile, commentato, sotto licenza Personal/Family/Pro
con permission a modificare per uso personale**.
