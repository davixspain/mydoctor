# MyDoctor Vault

Vault Obsidian personale per tracciare nel tempo:
- storia clinica continua
- referti, esami, visite
- diario sintomi quotidiano
- ipotesi diagnostiche aperte
- briefing per le visite mediche
- foto/documenti caricati via bot Telegram

## Come è organizzato

| Cartella / file | Contenuto |
|---|---|
| `00 Home.md` | dashboard di partenza con i link principali |
| `Profile.md` | la TUA identità, anagrafica, strutture sanitarie di riferimento — **da compilare** |
| `Timeline.md` | cronologia clinica completa in tabella |
| `Red Flags.md` | criteri per andare in PS / chiamare 112 (sempre visibili) |
| `Prossima visita.md` | briefing aggiornato da portare al medico curante |
| `Visits/` | ogni visita / procedura ospedaliera = una nota |
| `Labs/` | ogni sessione di analisi di laboratorio = una nota |
| `Conditions/` | "storie cliniche" attive |
| `Differentials/` | ipotesi diagnostiche con evidenze pro/contro e test per confermarle |
| `Medications/` | farmaci attivi e allergie |
| `Diagnostics pending/` | esami da richiedere e referti attesi |
| `Doctors/` | persone e strutture (rubrica) |
| `Symptom diary/` | nota quotidiana con sintomi del giorno + foto allegate |
| `Templates/` | modelli per nuove voci (visita, esame, sintomo) |
| `Attachments/YYYY-MM-DD/` | foto e PDF importati dal bot Telegram |

## Bot Telegram → Vault

Il bot privato `bot.py` riceve foto/documenti via Telegram e:
1. salva il file in `Attachments/YYYY-MM-DD/`
2. crea o aggiorna la nota `Symptom diary/YYYY-MM-DD.md` con l'embed dell'immagine
3. chiede a Claude (skill `mydoctor`) di analizzare il file e aggiornare le note pertinenti

## Convenzioni

- **Lingua**: italiano clinico
- **Date**: formato `YYYY-MM-DD` nei filename, `DD/MM/YYYY` nel testo
- **Tag**: `#visita`, `#esame`, `#sintomo`, `#farmaco`, `#allergia`, `#differenziale`, `#bandiera-rossa`, `#test-da-fare`, `#diario`, `#review-settimanale`, `#review-mensile`
- **Wikilink**: collegare ogni nota nuova alle entità esistenti (operatori, strutture, condizioni, ipotesi)
- Frontmatter YAML su ogni nota per metadata strutturate

## Mantenimento

Questo vault è una **fonte di verità mantenuta nel tempo**: ogni dato nuovo (sintomo, esame, farmaco, decisione) deve essere registrato qui contestualmente, non solo nella memoria di Claude. La memoria di Claude resta uno strato di lavoro; il vault è l'archivio storico.

## Per iniziare

Quando lanci il bot per la prima volta e digiti `/start`, MyDoctor entra in **modalità onboarding**: ti chiede di mandare TUTTE le info cliniche disponibili (foto referti, vocali, PDF, testo libero). Il bot le classifica e archivia in queste cartelle. Quando dici "basta" / "ho finito", produce una **sintesi clinica completa** e la registra in `Prossima visita.md`.
