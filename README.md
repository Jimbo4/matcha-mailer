# Matcha Mailer

Mailer semi-automatico per contattare i locali partner di [Matcha](https://www.matchadating.it). Parte dal funnel su Google Sheets e invia da `jacopo@matchadating.it` (Aruba). Nessuna mail parte senza la tua spunta e la tua conferma.

## Cosa fa

| Passo | Dettaglio |
|---|---|
| Legge il funnel | Foglio "Matcha - Funnel Vendita": colonne cercate per nome, righe cercate per nome del locale |
| Controlla le risposte | Cerca nella casella (solo intestazioni, niente viene aperto o segnato come letto) chi ha risposto e lo toglie dai follow up |
| Propone le azioni del giorno | Elenco con spunte e anteprima modificabile di oggetto e testo |
| Invia | SMTP Aruba, `info@matchadating.it` in copia, copia salvata in Posta inviata, mail 2 e 3 nello stesso thread della mail 1 |
| Registra | Aggiorna il funnel e scrive ogni modifica (valore vecchio → nuovo) nel Doc "Matcha - Funnel Vendita - cronologia modifiche" |
| WhatsApp | Per i locali senza mail ma con cellulare apre WhatsApp con il messaggio già scritto: premi tu invia |

## Regole della sequenza

| Locale nel funnel | Azione |
|---|---|
| `10 - nuovo`, con mail, non "TODO: da visitare" | Mail 1, poi Mail 2 dopo 4 giorni lavorativi, poi Mail 3 (break up) dopo altri 6 |
| `10 - nuovo` che ha risposto | Esce dalla sequenza: in grigio "Ha risposto", la leggi tu |
| `50 - curioso` con mail | Mail 4 con la lettera d'intenti in PDF (esportata dal Doc a ogni invio, quindi sempre aggiornata) |
| `50 - curioso` senza mail, con cellulare | WhatsApp con link alla lettera |
| `50 - curioso` con solo numero fisso | In grigio: da chiamare |
| `00 - perso`, con mail, non "TODO: da visitare", su tua richiesta | Come `10 - nuovo`: Mail 1, poi Mail 2 e Mail 3. Probabilità resta `00` |
| `90`, `00` (senza richiesta), "TODO: da visitare" | Nessuna azione |

### Ricontattare un locale perso

Di norma il mailer salta i locali `00 - perso`. Se vuoi scrivere comunque a uno di loro:

- **finestra:** spunta "Mostra anche i persi" in alto. I locali persi con una mail compaiono con la Mail 1 non spuntata: spunta solo quelli da ricontattare ("Seleziona tutte" non li include);
- **comandi:** aggiungi `--riattiva`, ad esempio `invia "Nome locale" --riattiva`. Vale solo per i locali indicati.

Nel funnel la Probabilità resta `00 - perso`; la sequenza prosegue da sola con Mail 2 e Mail 3 grazie a "Mail step", e le risposte vengono controllate come per gli altri. La cronologia segna "locale 00 - perso riattivato su richiesta".

Quando un locale non ha azioni, il mailer spiega il motivo e cosa fare (ad esempio: aggiungere la mail nel funnel, usare `--riattiva`, svuotare "Mail step").

I giorni lavorativi escludono weekend, festività nazionali, Pasquetta e Sant'Ambrogio. Oltre le 20 mail a settimana il mailer chiede conferma (non blocca). Tra un invio e l'altro fa una pausa casuale di 5-30 secondi, così le mail non partono a raffica. Soglia e pausa si cambiano in `config.ini`.

### Colonne aggiunte al funnel

| Colonna | Valori |
|---|---|
| Mail step | vuoto = mai scritto · `1` `2` `3` = mail della sequenza inviate · `4` = lettera inviata · `WA` = WhatsApp inviato · `stop` = non vuole essere contattato · `risposta` = ha risposto, sequenza chiusa |
| Mail ultimo invio | Data dell'ultimo invio |
| Mail prossimo invio | Data da cui parte la mail successiva |
| Mail thread | Identificativo tecnico della mail 1, serve a tenere il thread |

Per togliere a mano un locale dalla sequenza basta scrivere `stop` o `risposta` in "Mail step".

Nella colonna "Note" il mailer aggiunge dopo una virgola un frammento tipo "Email 1 inviata il 12/10/2026" e sostituisce il frammento precedente del mailer, senza toccare il resto della nota.

## Uso quotidiano

1. Doppio clic su **Matcha Mailer.bat**.
2. Controlla l'elenco: le righe spuntate sono quelle da inviare, quelle in grigio sono in attesa o da gestire a mano.
3. Clic su un locale per vedere e, se serve, modificare oggetto e testo. "Invia prova a me" ti manda la mail così come la riceverà il locale.
4. Le parti tra graffe rimaste vuote (es. `{numero_coppie}` nella mail 3) vanno completate: finché ci sono, la mail non parte.
5. **Invia selezionate** → riepilogo → conferma.
6. Per WhatsApp: seleziona il locale, **Apri WhatsApp**, invia dal telefono o dal PC, poi conferma nel mailer così aggiorna il funnel.

## Uso da Claude o da terminale

Gli stessi passaggi della finestra sono disponibili come comandi, così puoi chiedere gli invii a Claude Code aperto in questa cartella sul tuo PC. Le istruzioni e le regole per Claude sono in [`CLAUDE.md`](CLAUDE.md): nessun invio senza la tua conferma dopo l'anteprima.

```
.venv\Scripts\python -m matcha_mailer verifica
.venv\Scripts\python -m matcha_mailer stato
.venv\Scripts\python -m matcha_mailer anteprima "Nome locale"
.venv\Scripts\python -m matcha_mailer invia "Nome locale"              (anteprima, non invia)
.venv\Scripts\python -m matcha_mailer invia "Nome locale" --conferma   (invia)
.venv\Scripts\python -m matcha_mailer invia "Locale perso" --riattiva    (locale 00 - perso, su tua richiesta)
.venv\Scripts\python -m matcha_mailer password                         (salva la password Aruba, solo tu)
```

## Installazione (una volta)

### 1. File di configurazione

Al primo avvio il mailer crea `config.ini` da `config.example.ini`. Completa gli ID dei tre file Drive (la parte dell'URL tra `/d/` e `/edit`): funnel, cronologia, lettera_intenti_v2. `config.ini` non va su GitHub.

### 2. Accesso a Google

Serve un "client OAuth" personale, una volta sola, con l'account che vede il funnel.

1. Apri [console.cloud.google.com](https://console.cloud.google.com) e crea un progetto, ad esempio "Matcha Mailer".
2. In **API e servizi → Libreria** abilita **Google Sheets API**, **Google Docs API** e **Google Drive API**.
3. In **Google Auth Platform** (schermata consenso OAuth) configura un'app di tipo **Esterno** chiamata "Matcha Mailer" e aggiungi il tuo account Google tra gli **utenti di test**.
4. In **Client** crea un client OAuth di tipo **App desktop**, scarica il JSON, rinominalo `credentials.json` e mettilo nella cartella `secrets\`.
5. Al primo avvio si apre il browser: accedi, alla schermata "Google non ha verificato questa app" scegli Avanzate → Vai a Matcha Mailer (è la tua app) e accetta.

Con l'app in modalità test Google chiede di rifare l'accesso ogni 7 giorni: il mailer riapre il browser da solo.

### 3. Password Aruba

Al primo avvio il mailer chiede la password di `jacopo@matchadating.it` e la salva nel portachiavi di Windows (Gestione credenziali), non in un file. Se la cambi, il mailer te la richiede.

### 4. Collegamento sul desktop (facoltativo)

Tasto destro su `Matcha Mailer.bat` → Invia a → Desktop (crea collegamento).

### 5. Lettera d'intenti

Per il link nel WhatsApp, `lettera_intenti_v2` deve essere condivisa in sola lettura con "Chiunque abbia il link".

## Prima di partire: DNS di matchadating.it

I record sono su Vercel. Senza queste correzioni le mail rischiano lo spam.

| Record | Nome | Valore |
|---|---|---|
| SPF (TXT) | `@` | `v=spf1 include:_spf.aruba.it -all` (oggi ha un punto finale di troppo) |
| DKIM (TXT) | quello indicato da Aruba | Attiva DKIM nel pannello Aruba e copia il record |
| DMARC (TXT) | `_dmarc` | `v=DMARC1; p=none; rua=mailto:info@matchadating.it` |

## Modificare i testi

Tutti i testi, firma compresa, sono in [`testi_email.md`](testi_email.md): il mailer lo rilegge a ogni avvio e con "Aggiorna". In cima al file ci sono le regole per non romperlo.

## Cosa non c'è nel repo

`config.ini`, `secrets\` (credenziali Google e token), `data\` (registro invii e log) e i PDF sono esclusi da `.gitignore`. I dati dei locali restano nel funnel.

## Struttura

```
Matcha Mailer.bat      avvio con doppio clic (installa le librerie la prima volta)
CLAUDE.md              istruzioni e regole per usare il mailer da Claude
testi_email.md         testi delle mail, del WhatsApp e firma
config.example.ini     modello di configurazione
matcha_mailer/
  app.py               finestra (tkinter)
  cli.py               comandi da terminale (usati anche da Claude)
  keychain.py          password Aruba nel portachiavi di Windows
  engine.py            collega funnel, testi, invio e cronologia
  planner.py           regole della sequenza
  funnel.py            lettura e scrittura del foglio, righe per nome
  texts.py             lettura di testi_email.md e composizione testo/HTML
  mailbox.py           SMTP, copia in Inviati, controllo risposte IMAP
  google_api.py        accesso Google, PDF della lettera, cronologia
  calendar_it.py       giorni lavorativi a Milano
tests/                 test automatici (dati inventati)
```

## Sviluppo

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest
.venv\Scripts\python -m pytest
```
