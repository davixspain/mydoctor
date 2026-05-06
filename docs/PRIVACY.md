# 🔐 Privacy — dove vanno i tuoi dati

Documento essenziale. Leggilo prima di acquistare. MyDoctor gestisce dati
sanitari e devi sapere esattamente cosa succede ai tuoi.

---

## TL;DR (versione per chi ha fretta)

- ✅ I dati clinici **vivono sul tuo computer** in un vault Obsidian
- ✅ L'autore di MyDoctor **non riceve, non vede, non conserva** i tuoi dati
- ✅ Niente analytics, niente telemetria, niente "phone home"
- ⚠️ Tre servizi esterni partecipano alla pipeline: **Telegram**, **Anthropic**,
  e **Apple/Google** (solo se usi i loro app store / sistema operativo)
- ✅ Hai **controllo totale**: puoi disabilitare ogni componente, fare backup,
  cancellare tutto, esportare in qualsiasi momento

---

## Architettura privacy

```
   I TUOI DATI VIVONO QUI                    PASSANO DI QUI
   ════════════════════                      ════════════════
   ~/MyDoctor/vault/                          Telegram (transito)
   ~/MyDoctor/logs/                           Anthropic (inferenza)
   ~/.claude/projects/-.../memory/

   QUI NON CI ARRIVANO MAI
   ═══════════════════════
   • Server dell'autore di MyDoctor (non esistono)
   • Server di analytics
   • Cloud storage di terze parti (a meno che tu lo configuri)
```

---

## Dove vivono i tuoi dati (locale)

Tutto sul tuo disco fisso, sotto il tuo account utente:

| Path | Contenuto | Permessi consigliati |
|---|---|---|
| `~/MyDoctor/vault/` | Vault Obsidian: tutte le note cliniche, foto, PDF | 700 (default) |
| `~/MyDoctor/logs/` | Log applicativi (testo) | 600 |
| `~/MyDoctor/.env` | Token Telegram + chat_id | 600 (impostato dall'installer) |
| `~/MyDoctor/.session_id` | UUID sessione Claude corrente | 600 |
| `~/.claude/projects/-.../memory/` | Memoria di lavoro Claude | gestito da Claude |

**Conseguenza pratica**: se faccio un backup della mia home, sto facendo backup
di tutto MyDoctor incluso. Se cancello `~/MyDoctor/`, ho cancellato tutto.

---

## Servizi esterni che partecipano

### 1. Telegram (Telegram FZ-LLC)

**Perché**: il bot riceve i tuoi messaggi via Telegram Bot API.

**Cosa passa**:
- Tutti i messaggi che mandi al bot (testo, foto, documenti, vocali)
- Tutti i messaggi che il bot ti manda

**Dove viene archiviato**:
- I messaggi vengono memorizzati nei server Telegram secondo la loro privacy
  policy. Telegram ha un'opzione "Secret Chats" end-to-end **non** disponibile
  per i bot. La chat con il bot **non è E2E encrypted**.
- Telegram cancella i media dal cloud quando lo richiedi tramite "Clear Chat",
  ma le copie scaricate dal bot sul tuo PC restano.

**Cosa fare se preferisci NON usare Telegram**:
- Usa il vault direttamente con Obsidian (puoi scrivere note a mano)
- Modifica `bot.py` per usare un'altra interfaccia (es. CLI locale,
  email, file watcher)

### 2. Anthropic Claude API (Anthropic PBC)

**Perché**: il ragionamento clinico è delegato a Claude (modello LLM di
Anthropic). Quando il bot lancia il subprocess `claude`, sta facendo
chiamate HTTPS all'API Anthropic.

**Cosa passa**:
- Il PRIMER + il prompt utente + il contenuto dei file che Claude legge
  (referti medici, foto, ecc.)
- Anthropic processa la richiesta, restituisce una risposta

**Politica di Anthropic** (al momento della pubblicazione di MyDoctor 1.0):
- Per Claude Code consumer: input/output **non** usati per addestrare modelli
  per default
- I dati possono essere conservati per un tempo limitato per safety review
  e abuse detection
- Vedi [anthropic.com/legal/privacy](https://www.anthropic.com/legal/privacy)
  per la versione corrente

**Cosa fare se preferisci NON inviare dati ad Anthropic**:
- MyDoctor non funziona senza un LLM. Il vault e la struttura sono tuoi, ma
  l'analisi automatica delle foto/referti richiede inferenza.
- Alternativa: usa il vault come archivio passivo (lo apri in Obsidian, scrivi
  manualmente le valutazioni). Disabilita il bot.

### 3. Telegram → Anthropic via il tuo bot

Quando una foto arriva via Telegram:
1. Telegram → server Telegram (HTTPS)
2. Tuo bot la scarica → file locale (HTTPS, dal tuo PC)
3. Claude la legge dal file locale → API Anthropic (HTTPS)

**Doppio passaggio**: i dati passano attraverso entrambe le infrastrutture
prima di tornare a te. Devi essere a tuo agio con entrambe le privacy policies.

---

## Cosa MyDoctor NON fa

- ❌ **Niente telemetria**. Il prodotto non manda nulla all'autore di MyDoctor.
  Cerca pure nel codice: nessuna `requests.post()` verso domini esterni a
  Telegram e Anthropic.
- ❌ **Niente account**. Non c'è registrazione, login, profilo cloud.
- ❌ **Niente cookie / tracker**. Non c'è una webapp.
- ❌ **Niente sync automatico** verso cloud (a meno che tu configuri un cloud
  storage manualmente sopra al vault — è una tua scelta).
- ❌ **Niente accesso ai tuoi dati per il supporto**. Per debug, ti chiediamo
  di mandarci log specifici **che decidi tu** di condividere.

---

## Compliance

### GDPR (Italia/UE)

- **Titolare del trattamento**: TU. I dati sono sul tuo PC.
- **Responsabili del trattamento** (third-party processors a cui passi i dati
  attivamente): Telegram FZ-LLC, Anthropic PBC.
- L'autore di MyDoctor **non è né titolare né responsabile** dei tuoi dati,
  perché non li riceve.

### Diritti dell'utente

- **Diritto di accesso**: aprire `~/MyDoctor/vault/` in qualsiasi editor.
- **Diritto di rettifica**: modificare i file markdown a mano.
- **Diritto alla cancellazione**: `rm -rf ~/MyDoctor/`. Per cancellare i dati
  Telegram → "Clear Chat" + "Delete Chat" sul lato Telegram. Per Anthropic →
  vedi [Data Deletion Request](https://privacy.anthropic.com/).
- **Diritto alla portabilità**: il vault è già portabile, è una cartella di
  file `.md` zippabile. `tar czf vault-backup.tar.gz ~/MyDoctor/vault/`.

### Sensitive data

I dati sanitari sono "categoria particolare" (Art. 9 GDPR). MyDoctor:
- Non li centralizza
- Non li trasferisce a paesi terzi (a meno che tu usi servizi che lo fanno —
  Telegram e Anthropic potrebbero processare in regioni extra-UE)
- Te lo dichiara esplicitamente in questo documento

---

## Best practices per gli utenti attenti alla privacy

### Massima privacy (paranoid mode)

1. **Non usare Telegram** — disabilita `bot.py`, usa il vault solo
   manualmente con Obsidian.
2. **Non usare Anthropic** — accetta di rinunciare all'analisi automatica.
   Il vault diventa un diario clinico cartaceo digitale.
3. **Cripta il disco** — full-disk encryption (LUKS/Linux, FileVault/macOS,
   BitLocker/Win) protegge il vault a riposo.
4. **Backup cifrato** — backup del vault con `restic`/`borg` cifrato.

### Privacy ragionevole (default consigliato)

1. **`.env` con permessi 600** (l'installer lo fa)
2. **Vault sotto la tua home utente** (l'installer lo fa)
3. **Telegram: usa un account dedicato se vuoi separazione massima**
4. **Backup mensile** in posto sicuro (disco esterno cifrato, NAS in casa,
   cloud cifrato lato client come Cryptomator)

### Privacy "normale" (la maggioranza degli utenti)

Lascia i default dell'installer. È già più privato del 99% dei prodotti
medical-tech che esistono.

---

## In caso di compromissione

Se sospetti che il tuo PC sia stato compromesso:

1. **Disconnetti la macchina** dalla rete
2. **Revoca il token Telegram** via @BotFather → `/revoke` → seleziona il bot
   - Il vecchio token diventa invalido immediatamente
   - Il nuovo va aggiornato nel `.env`
3. **Cambia password Anthropic** se sospetti il login compromesso
4. **Controlla i log** di `~/MyDoctor/logs/` per attività anomala
5. **Backup del vault** su supporto pulito prima di reinstallare il sistema

---

## Domande?

Email al supporto (per clienti **Pro**): vedi `LICENSE.md`. Riceverai risposta
in 24h lavorativi senza dover condividere alcun dato sensibile.

Per i clienti Personal/Family: la community di utenti e la documentazione sono
i canali principali. Per problemi privacy gravi, scrivi comunque — leggiamo
ogni email.
