# ❓ Domande frequenti

Le domande che ci fanno più spesso. Se la tua non c'è, scrivi al supporto
(clienti Pro) o consulta [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Cos'è esattamente MyDoctor?

Un **assistente clinico AI personale** che gira sul tuo computer. Riceve via
Telegram foto di referti, sintomi, vocali, PDF. Li archivia in un vault
Obsidian strutturato. Trova pattern temporali sui tuoi dati. Ti prepara prima
delle visite mediche reali con un briefing pronto da mostrare al dottore.

Non è:
- Un dispositivo medico certificato
- Un sostituto del medico
- Una piattaforma cloud / SaaS

È:
- Un tool di **organizzazione e memoria** della tua salute
- Un **assistente di osservazione** che vede pattern che tu non vedresti
- Un **preparatore alle visite** che sintetizza la tua storia

---

## Posso fare diagnosi con MyDoctor?

**No.** MyDoctor produce sintesi strutturate dei dati che tu fornisci e
nomina ipotesi diagnostiche da **discutere con il tuo medico**. Tutte le
diagnosi vere devono essere fatte da un medico abilitato dopo visita
clinica e esami opportuni.

Vedi disclaimer in [LICENSE.md](../LICENSE.md) sezione 4.

---

## Su quali sistemi operativi gira?

- ✅ **Linux** (Ubuntu/Debian/Arch/Fedora) testato
- ✅ **macOS** 13+ (Apple Silicon e Intel)
- ✅ **Windows** 10/11 (con Python nativo o WSL2)
- ✅ **Mobile via Telegram** (iOS/Android — apri il bot, è già un'app
  utilizzabile dal cellulare)

App native iOS/Android sono in **roadmap v2.0** — vedi
[ROADMAP.md](../ROADMAP.md).

---

## Quanto costa Claude API ogni mese?

Dipende da quanto usi il bot:
- **Uso leggero** (qualche foto al giorno, review settimanale): ~$2–5/mese
  con Claude Sonnet
- **Uso intenso** (decine di referti al mese + onboarding completo): ~$10–20/mese
- **Onboarding iniziale** (carichi tutta la storia): ~$5–10 una tantum

Il costo è interamente di Anthropic, non dell'autore di MyDoctor. Hai
controllo totale: setti un budget mensile sul tuo account Anthropic.

---

## Posso usare MyDoctor senza Internet?

Per:
- **Editare manualmente il vault con Obsidian** → SI, è offline
- **Leggere i tuoi referti già caricati** → SI, sono file locali
- **Ricevere/mandare messaggi col bot** → NO, serve internet (Telegram +
  Anthropic API)
- **Le review schedulate** → NO, idem

Per uso offline puro, il vault Obsidian funziona da solo come archivio.

---

## Cosa succede ai miei dati medici?

Vedi [PRIVACY.md](PRIVACY.md) — è il documento più importante prima
dell'acquisto.

In breve:
- Vivono sul tuo PC nel vault `~/MyDoctor/vault/`
- L'autore di MyDoctor **non li riceve mai**
- Passano attraverso Telegram (per i messaggi) e Anthropic (per il
  ragionamento) — devi accettare le loro privacy policy
- Niente cloud, niente account, niente telemetria

---

## È legale usarlo per la mia salute?

**Sì**, come strumento personale di gestione dei dati. Non è un dispositivo
medico → non richiede certificazione CE/FDA. È equivalente a un diario
clinico cartaceo che tu mantieni per te stesso.

Quello che non è legale:
- Vendere consulenze cliniche basate sull'output di MyDoctor (saresti tu a
  esercitare abusivamente la medicina)
- Usarlo come unica fonte per decisioni cliniche urgenti

---

## Posso condividere il vault con il mio medico?

Sì. Modi pratici:
- **Stampa** `Prossima visita.md` → la consegni cartacea
- **Export PDF** da Obsidian (`Ctrl+P` → "Export to PDF") → email al medico
- **Share-link Obsidian Sync** (servizio a parte di Obsidian, opzionale)
- **Cartella shared** (Dropbox/Google Drive/iCloud sopra al vault — sotto
  la tua responsabilità privacy-wise)

Versione 3.0 in roadmap: integrazione con FSE (Fascicolo Sanitario
Elettronico) Italia.

---

## Posso usarlo per più persone della mia famiglia?

- **Personal license** (€49): 1 utente
- **Family license** (€99): fino a 4 utenti, ognuno con la propria
  installazione e il proprio vault

Ogni installazione è indipendente: un vault per persona, separati. Non
condividere lo stesso bot Telegram tra più persone — il chat_id ACL accetta
solo un OWNER per volta.

---

## Cosa succede se finisce la batteria del PC?

Il bot non gira → non ricevi risposte. I messaggi che mandi a Telegram
restano in coda lato Telegram per **24 ore**. Quando riaccendi il PC e il
servizio riparte, il bot processa gli arretrati.

I timer schedulati hanno `Persistent=true` (Linux) o equivalenti: una review
saltata viene rilanciata al prossimo avvio del PC.

---

## Posso versionare il vault con git?

Sì, è un caso d'uso ottimo:
```bash
cd ~/MyDoctor/vault
git init
git add .
git commit -m "initial"
```

Markdown comprime bene, ogni cambio è leggibile come diff. Puoi fare push
su un repo privato GitLab/GitHub/Codeberg per backup, **ma valuta privacy
implications** — sono dati sanitari.

---

## Come faccio backup?

```bash
# Manuale, una tantum
tar czf vault-backup-$(date +%Y%m%d).tar.gz ~/MyDoctor/vault/

# Automatico mensile via cron
echo '0 3 1 * * tar czf ~/Backups/mydoctor-$(date +\%Y\%m).tar.gz ~/MyDoctor/vault' | crontab -
```

Tool consigliati per backup cifrati incrementali: `restic`, `borgbackup`,
`rclone` con encryption.

---

## Posso modificare i prompts/skill?

Sì, è incluso nei termini della licenza Personal/Family/Pro: modifica per
**uso personale**. Non puoi ridistribuire la versione modificata.

File chiave da modificare:
- `~/MyDoctor/src/bot.py` — PRIMER (riga ~120)
- `~/.claude/skills/mydoctor/SKILL.md` — comportamento clinico

Riavvia il servizio dopo le modifiche (`systemctl --user restart mydoctor`).

---

## Posso aggiungere altre lingue oltre l'italiano?

Sì. Modifica:
1. `SKILL.md` → cambia "Respond in Italian" con la tua lingua
2. PRIMER in `bot.py` → traduci
3. Templates del vault → traduci

Versione 1.1 supporterà bilingue out-of-the-box (vedi
[ROADMAP.md](../ROADMAP.md)).

---

## Cosa fa il review settimanale esattamente?

Ogni domenica alle 20:00 il sistema lancia Claude in modalità non
interattiva con un prompt che dice:

> Leggi il diario degli ultimi 7 giorni. Confrontalo coi 30 precedenti.
> Cerca pattern alimento→sintomo, cluster, drift, segni di pericolo.
> Se trovi qualcosa di rilevante → scrivi un messaggio Telegram.
> Se nulla → silenzio.

Esempio reale di output:

> 📊 Riepilogo settimanale 22–29/04
>
> Pattern osservati:
> • Hai mangiato pizza 3 volte e ogni volta hai avuto gonfiore il giorno
>   dopo. Pattern già noto rinforzato.
>
> Nuovi elementi:
> • Mai avuto reazione orofaringea con la pizza, anche dopo 4 birre. Conferma
>   che il trigger orofaringeo richiede cofattori specifici.
>
> Da portare al medico: prescrizione EpiPen ancora aperta da 3 settimane.

---

## Il bot mi disturberà di continuo?

No. La filosofia è:
- **Reattivo** quando gli scrivi → risposta veloce
- **Proattivo** solo se trova qualcosa di rilevante → silenzio quando nulla
  cambia

Le review schedulate **non sempre producono un messaggio**. Settimane
clinicamente piatte = silenzio. Solo segnali significativi rompono il
silenzio.

Se vuoi disabilitare il push proattivo (ma mantenere le review come audit
log nel vault):
```bash
# Nel ~/MyDoctor/.env aggiungi
MYDOCTOR_DISABLE_PROACTIVE_PUSH=1
```

---

## Posso testare prima di comprare?

Garanzia rimborso 14 giorni se l'installazione non riesce sul tuo sistema
supportato. Vedi [LICENSE.md](../LICENSE.md) sezione 7.

---

## Quando esce la versione mobile?

App native iOS/Android in roadmap **v2.0**, target **Q4 2026 / Q1 2027**.
Vedi [ROADMAP.md](../ROADMAP.md). I clienti v1.0 ricevono **30% di sconto**
sull'add-on mobile quando esce.

Nel frattempo: usa Telegram dal cellulare. Funziona perfettamente.

---

Altre domande? Scrivi al supporto.
