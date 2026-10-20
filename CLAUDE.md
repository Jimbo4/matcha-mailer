# Matcha Mailer · istruzioni per Claude

Questo progetto invia le mail commerciali di Matcha ai locali partner (bar, cocktail bar, wine bar, pub di Milano) a nome di Jacopo, CMO & Co-founder, da `jacopo@matchadating.it` (casella Aruba). Parte dal Google Sheet "Matcha - Funnel Vendita", aggiorna il funnel e scrive ogni modifica nel Doc "Matcha - Funnel Vendita - cronologia modifiche".

Il mailer funziona **solo sul PC di Jacopo**: lì ci sono la password Aruba (nel portachiavi di Windows) e l'accesso Google (`secrets/`). Una chat nel cloud non può inviare: non ha le credenziali e non raggiunge il server SMTP di Aruba. Se non sei in esecuzione sul suo PC, nella cartella del mailer, dillo subito a Jacopo e non tentare altre strade.

## Regole da rispettare sempre

1. **Nessun invio senza l'ok esplicito di Jacopo**, dato dopo aver visto l'anteprima completa di ogni mail (destinatario, copia, oggetto, testo). Un "ok" dato prima dell'anteprima non vale. Se Jacopo cambia qualcosa, rimostra l'anteprima e chiedi di nuovo.
2. Ogni invio passa da due comandi: prima `invia` **senza** `--conferma` (anteprima, non invia nulla), poi lo stesso comando **con** `--conferma`.
3. **Invia e registra solo con il mailer.** Non mandare mail con altri strumenti (Gmail, Resend, altri SMTP o API) e non registrare invii modificando a mano funnel o cronologia.
4. **Soglia settimanale (20 mail):** se il comando segnala che si supera, chiedi a Jacopo. Usa `--oltre-soglia` solo con il suo ok.
5. **Password e segreti:** non chiedere, leggere, stampare o copiare la password Aruba né i file in `secrets/`. Il comando `password` lo esegue Jacopo in un suo terminale: puoi aprirglielo con il comando già scritto (pannello Terminale dell'app), ma la password la digita lui e tu non leggi quel terminale finché non ti dice che ha finito.
6. **Git:** mai committare `config.ini`, `secrets/`, `data/` o PDF. Il repo è pubblico.
7. **Funnel:** le righe si cercano sempre per nome del locale, mai per numero di riga (il foglio viene riordinato). Il mailer lo fa da solo. Per ogni modifica al funnel che fai tu, anche fuori dal mailer (Probabilità, note, nuovi locali, menu a tendina, correzioni):
   - **prima di scrivere**, rileggi la riga e controlla che nella colonna "Nome attività" ci sia esattamente il locale giusto; se il nome non corrisponde o ci sono più righe con lo stesso nome, non scrivere e chiedi a Jacopo;
   - non sovrascrivere dati esistenti; nelle note riassumi il contenuto precedente (o toglilo se non serve più) e aggiungi la nuova nota dopo una virgola;
   - **dopo aver scritto**, rileggi la riga per nome e verifica che i valori siano quelli attesi;
   - aggiorna sempre il Doc "Matcha - Funnel Vendita - cronologia modifiche" (stessa cartella Drive del funnel), che fa da backup: sotto la data del giorno, un titolo e un punto per locale con colonna, valore vecchio e valore nuovo, così ogni modifica si può annullare. Il mailer lo fa da solo per invii, WhatsApp e `segna`; per le altre modifiche usa `engine.Session.write_history` (come fa il mailer) o lo strumento Google Docs.
8. **Risposte dei locali:** le legge Jacopo. Quando ti dice l'esito, chiudi la sequenza con `segna` e fai le altre modifiche al funnel che ti chiede.
9. **Testi:** cambia `testi_email.md` solo su richiesta di Jacopo. Per modificare una sola mail usa `--oggetto` e `--testo-file`, senza toccare il file dei testi.
10. **Come rispondere a Jacopo:** in italiano, sintetico, con tabelle quando servono, senza trattino lungo. Prima di iniziare dichiara il piano in una riga e segnala subito ostacoli o cambi di piano.
11. **Se manca qualcosa, spiega le operazioni da fare.** Quando un comando si ferma perché manca qualcosa (installazione, `.venv`, `config.ini`, credenziali, password, dati nel funnel, locale fuori sequenza), non fermarti a "manca X": dai a Jacopo l'elenco ordinato delle operazioni, per ognuna chi la fa (tu o lui), dove e come verificarla. Fai subito quelle che puoi fare tu senza violare le altre regole, poi chiedi l'ok per il resto. Il mailer stesso spiega il motivo nei messaggi d'errore: riportalo e completalo.
12. **Locali `00 - perso`:** il mailer li salta. Si ricontattano solo se Jacopo lo chiede per quel locale: allora aggiungi `--riattiva` ad `anteprima`, `prova` e `invia`. Non usarlo di tua iniziativa e non per gruppi di locali non nominati. La Probabilità resta `00`: non cambiarla a meno che Jacopo non lo chieda.
13. **Documentazione aggiornata:** quando in chat emergono informazioni nuove sul mailer, sull'installazione o su come lavorare con Jacopo (cose fatte una volta per tutte, preferenze, procedure), aggiorna nello stesso turno `README.md` (per Jacopo) e `CLAUDE.md` (per te). Mai dati dei locali, ID dei file o segreti: il repo è pubblico.

## Prerequisiti

| Cosa | Dove | Come verificarlo |
|---|---|---|
| Python e ambiente `.venv` | cartella del mailer | Se `.venv` manca: crealo tu con `py -3 -m venv .venv` e `.venv/Scripts/python -m pip install -r requirements.txt` (o Jacopo fa doppio clic su `Matcha Mailer.bat`) |
| `config.ini` | cartella del mailer (non nel repo) | `verifica` |
| `secrets/credentials.json` | client OAuth Google (README, "Accesso a Google: client OAuth") | `verifica` |
| Token Google | `secrets/token.json`, creato al primo accesso | Se manca o è scaduto, il primo comando apre il browser: avvisa Jacopo che deve fare l'accesso |
| Password Aruba | portachiavi di Windows | `verifica`; se manca, Jacopo esegue `.venv\Scripts\python -m matcha_mailer password` |

All'inizio di ogni sessione esegui `verifica` e riporta a Jacopo solo le righe "NO". Prima installazione sul PC di Jacopo completata il 20/10/2026: se ora `verifica` dà "NO", di solito è il token Google scaduto (ogni 7 giorni) o la password Aruba cambiata, non un'installazione da rifare.

DNS di matchadating.it (SPF, DKIM, DMARC): già configurati, non segnalarli come da fare.

## Prima installazione: cosa fai tu e cosa fa Jacopo

Se `verifica` segnala che manca qualcosa, dividi il lavoro così (regola 11) e fai subito la tua parte.

| Passo | Chi | Come |
|---|---|---|
| `.venv` e librerie | Tu | Comandi nella tabella Prerequisiti |
| `config.ini` | Tu | `verifica` lo crea dal modello. Se hai lo strumento Google Drive, cerca per titolo "Matcha - Funnel Vendita" (foglio), "Matcha - Funnel Vendita - cronologia modifiche" e "lettera_intenti_v2" (Doc), inserisci gli ID e controlla che il foglio si chiami `Sheet1`. Gli ID restano solo in `config.ini`, mai nel repo |
| Cartella `secrets/` | Tu | Creala vuota; non metterci né leggere file |
| Client OAuth (`secrets/credentials.json`) | Jacopo | **Non lo fai tu**, nemmeno con il browser: richiede l'accesso a Google Cloud con il suo account, l'accettazione dei termini e il download di un segreto. Guidalo un passo alla volta seguendo il README ("Accesso a Google: client OAuth"): dai un passo o due per messaggio, con link diretti e nomi esatti dei pulsanti, aspetta che ti dica com'è andata e aiutalo se la schermata è diversa. Alla fine lancia tu `verifica` |
| Password Aruba | Jacopo | **Non la digiti tu.** Aprigli un terminale con `.venv\Scripts\python -m matcha_mailer password` già pronto, indicando sempre come cartella di lavoro quella del mailer (`matcha-mailer`, non la cartella superiore `mailer`, altrimenti `.venv` non si trova); lui digita la password. Poi lancia tu `verifica` |
| Primo accesso Google | Tu lanci, Jacopo accede | Avvisalo prima che si aprirà il browser (account Google personale di Jacopo, "Avanzate" → "Vai a Matcha Mailer", spunta tutti gli accessi), poi lancia `verifica` (apre il browser da solo dopo aver trovato `credentials.json`) e attendi che finisca; rilancia `verifica` per conferma |

Account Google da usare: quello **personale** di Jacopo (vede funnel, cronologia e lettera; il funnel è di proprietà di Umberto e condiviso con Jacopo). Non scrivere il suo indirizzo personale nel repo: è pubblico.

## Come lanciare i comandi

Dalla cartella del mailer:

```bash
# Git Bash (Claude Code su Windows)
.venv/Scripts/python -m matcha_mailer <comando>
```
```powershell
# PowerShell
.venv\Scripts\python -m matcha_mailer <comando>
```

Senza comando (`python -m matcha_mailer`) si apre la finestra con le spunte: è per Jacopo, non per te.

| Comando | Cosa fa | Modifica qualcosa? |
|---|---|---|
| `verifica [--offline]` | Controlla configurazione, credenziali, accesso a funnel e Aruba | No |
| `stato [--json]` | Azioni da fare oggi e locali in attesa o da gestire a mano | No |
| `anteprima "Locale"` | Mostra destinatari, oggetto e testo con firma | No |
| `prova "Locale"` | Invia la mail solo a jacopo@matchadating.it, con "[PROVA]" nell'oggetto | Solo una mail a Jacopo |
| `invia "Locale" ["Altro locale" ...]` | Senza `--conferma`: anteprima e riepilogo, niente invii | No |
| `invia ... --conferma` | Invia, salva la copia in Posta inviata, aggiorna funnel e cronologia | Sì |
| `anteprima`/`prova`/`invia "Locale" --riattiva` | Tratta i locali `00 - perso` indicati come `10 - nuovo` (solo su richiesta di Jacopo) | Come il comando senza opzione |
| `whatsapp "Locale" [--apri]` | Testo e link WhatsApp pronti (Jacopo invia dal telefono) | No |
| `whatsapp "Locale" --inviato` | Registra il WhatsApp inviato in funnel e cronologia | Sì |
| `segna "Locale" risposta\|stop [--conferma]` | Chiude la sequenza del locale | Sì, con `--conferma` |
| `password` | Salva la password Aruba | Solo Jacopo, in un suo terminale |

Opzioni utili per `anteprima`, `prova` e `invia`:
- `--valore nome=valore` completa una parte tra graffe, ad esempio `--valore numero_coppie=12`. Si può ripetere.
- `--oggetto "..."` e `--testo-file percorso.txt` sostituiscono oggetto e testo di **una sola** mail. Scrivi il file in UTF-8 nella cartella temporanea di sistema, non nella cartella del mailer. La firma si aggiunge da sola.

Codici di uscita: `0` fatto, `1` errore (leggi il messaggio), `2` niente fatto perché manca `--conferma` (o `--oltre-soglia`, o `--inviato`).

## Procedure

**"Manda la mail a [locale]"**
1. `verifica`, se non l'hai già fatto in questa sessione.
2. `invia "[locale]"` senza `--conferma`. Se il locale non ha azioni oggi, riporta a Jacopo il motivo e le operazioni che il comando indica (regola 11). Se è `00 - perso`, chiedigli se vuole ricontattarlo: con il suo sì rilancia con `--riattiva`.
3. Mostra a Jacopo l'anteprima completa. Se ci sono parti tra graffe da completare, chiedigli i valori.
4. Aspetta l'ok esplicito.
5. `invia "[locale]" --conferma` con le eventuali `--valore`.
6. Riporta l'esito: inviata o non inviata, funnel aggiornato, cronologia aggiornata, eventuali avvisi.

**"Cosa c'è da fare oggi?"**
1. `stato`, poi una tabella per Jacopo: locale, zona, azione, destinatario.
2. Jacopo sceglie i locali, poi anteprima di ciascuno e ok.
3. Un solo comando `invia "A" "B" "C" --conferma`: il mailer mette da solo una pausa casuale di 5-30 secondi tra un invio e l'altro.

**"Fammi una prova"**: `prova "[locale]"`. Non tocca funnel né cronologia.

**WhatsApp**: `whatsapp "[locale]"`, dai a Jacopo il link (o usa `--apri`); quando ti conferma di averlo inviato, `whatsapp "[locale]" --inviato`.

**"Mi ha risposto [locale]"**: chiedi l'esito se non è chiaro. Poi `segna "[locale]" risposta --conferma` (o `stop` se ha chiesto di non essere più contattato) e le altre modifiche al funnel che Jacopo chiede (ad esempio Probabilità "50 - curioso").

**Un locale non compare**: il mailer considera i locali con Probabilità `10 - nuovo` (con mail, non "TODO: da visitare"), `50 - curioso` e, solo su richiesta, `00 - perso`. Il messaggio d'errore dice il motivo e cosa fare: riportalo a Jacopo come elenco di operazioni (regola 11).

**"Riscrivi a [locale perso]"**: `invia "[locale]" --riattiva` senza `--conferma`, anteprima a Jacopo, ok, poi con `--conferma`. Probabilità resta `00`; Mail 2 e 3 seguono da sole.

## Regole della sequenza

| Locale nel funnel | Azione proposta |
|---|---|
| `10 - nuovo`, con mail, non "TODO: da visitare", mai scritto | Mail 1 |
| `10 - nuovo`, Mail step `1`, dalla data in "Mail prossimo invio" (4 giorni lavorativi dopo) | Mail 2, nello stesso thread |
| `10 - nuovo`, Mail step `2`, dalla data in "Mail prossimo invio" (6 giorni lavorativi dopo) | Mail 3 (break up), nello stesso thread |
| `10 - nuovo` che ha risposto (controllo automatico della casella) | Nessuna: "Ha risposto", la legge Jacopo |
| `50 - curioso` con mail | Mail 4 con la lettera d'intenti in PDF |
| `50 - curioso` senza mail, con cellulare | WhatsApp con link alla lettera |
| `50 - curioso` con solo numero fisso | Nessuna: da chiamare |
| `00 - perso`, con mail, non "TODO: da visitare", su richiesta di Jacopo (`--riattiva` o spunta nella finestra) | Come `10 - nuovo`: Mail 1, poi Mail 2 e 3 da "Mail step". Probabilità resta `00` |
| `90`, `00` senza richiesta, Mail step `3`, `4`, `WA`, `stop`, `risposta` | Nessuna |

Colonne del mailer nel funnel: `Mail step`, `Mail ultimo invio`, `Mail prossimo invio`, `Mail thread` (identificativo tecnico della mail 1, non toccarlo). In "Ultima azione fatta" scrive `Email automatica 1`/`2`/`3 (break up)`, `Email automatica lettera d'intenti` o `WhatsApp automatico lettera d'intenti`: sono nel menu a tendina della colonna (convalida rigida). Se cambi questi valori in `planner.py` (`LAST_ACTION_VALUE`), aggiorna anche il menu del funnel (colonna H, tutte le righe), mantenendo valori manuali e colori, e registra la modifica in cronologia. In "Note" il mailer aggiunge "Email automatica N inviata il gg/mm/aaaa" dopo una virgola e sostituisce il proprio frammento precedente (riconosce anche il vecchio formato "Email N inviata il").

## Testi

Tutti i testi e la firma sono in `testi_email.md`, letto a ogni comando; in cima al file ci sono le regole per non romperlo. Le parti tra graffe le riempie il mailer. `{numero_coppie}` nella mail 3 va sempre chiesto a Jacopo: finché manca, la mail non parte. Se manca `{n_locali}` (nessun locale firmato nel funnel), chiedi a Jacopo prima di procedere.

## File

| File | Cosa contiene |
|---|---|
| `config.ini` | Mittente, copia (info@matchadating.it), server Aruba, ID dei file Drive, giorni della sequenza, soglia settimanale, pausa tra invii |
| `testi_email.md` | Testi delle mail, WhatsApp, firma |
| `data/invii.csv` | Registro locale di ogni invio. Serve anche a non riproporre una mail partita ma non registrata nel funnel |
| `data/mailer.log` | Log tecnico |
| `secrets/` | Credenziali Google: non leggere, non copiare |

## Problemi frequenti

| Messaggio | Cosa fare |
|---|---|
| "Password Aruba non salvata" | Jacopo esegue il comando `password` in un suo terminale |
| "Manca credentials.json" | Guida Jacopo passo passo nel README, sezione "Accesso a Google: client OAuth" (vedi "Prima installazione") |
| Si apre il browser di Google | Normale al primo uso o a token scaduto (ogni 7 giorni in modalità test): Jacopo fa l'accesso |
| "più righe con lo stesso nome" | Nel funnel ci sono due righe con lo stesso nome: chiedi a Jacopo quale tenere, il mailer non scrive finché non sono distinte |
| "nessuna azione da fare oggi" | Il locale è in attesa (vedi la data) o fuori sequenza: riporta motivo e operazioni indicate dal messaggio |
| "è segnato \"00 - perso\"" | Chiedi a Jacopo se vuole ricontattarlo; se sì, `--riattiva` |
| `.venv` mancante (il comando python non parte) | Jacopo fa doppio clic su `Matcha Mailer.bat` una volta (crea `.venv` e installa le librerie) |
| "Ho creato config.ini dal modello" / "In config.ini mancano" | Inserisci gli ID dei file Drive (parte dell'URL tra `/d/` e `/edit`): funnel, cronologia, lettera_intenti_v2. Cercali tu su Drive per titolo se hai lo strumento, poi rilancia `verifica` |
| "inviata ma funnel NON aggiornato" | La mail è partita: con l'ok di Jacopo aggiorna a mano la riga (per nome) con i valori che il mailer avrebbe scritto, e aggiungi una voce alla cronologia |
| "copia in Inviati non salvata" | La mail è partita: avvisa Jacopo, non reinviarla |
| Login Aruba rifiutato | Password cambiata: Jacopo riesegue `password` |

## Sviluppo

- Codice in `matcha_mailer/`: `cli.py` (comandi), `app.py` (finestra), `engine.py` (logica comune), `planner.py` (regole della sequenza), `funnel.py` (foglio, righe per nome), `texts.py` (testi), `mailbox.py` (SMTP e IMAP Aruba), `google_api.py` (Google), `calendar_it.py` (giorni lavorativi a Milano).
- Test: `.venv/Scripts/python -m pip install pytest` e poi `.venv/Scripts/python -m pytest`. I dati di test sono inventati: non mettere nel repo nomi, mail o telefoni reali dei locali.
- Ogni modifica al comportamento va coperta da un test e descritta nel README.
