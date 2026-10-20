# Matcha Mailer

Mailer semi-automatico per contattare i locali partner di [Matcha](https://www.matchadating.it). Parte dal funnel su Google Sheets e invia da `jacopo@matchadating.it` (Aruba). Nessuna mail parte senza la tua spunta e la tua conferma.

## Cosa fa

| Passo | Dettaglio |
|---|---|
| Legge il funnel | Foglio "Matcha - Funnel Vendita": colonne cercate per nome, righe cercate per nome del locale |
| Controlla le risposte | Cerca nella casella chi ha risposto e lo toglie dai follow up. Con il comando `risposte` legge anche il testo (senza segnare le mail come lette), così Claude può riassumerle |
| Propone le azioni del giorno | Elenco con spunte e anteprima modificabile di oggetto e testo |
| Invia | SMTP Aruba, `info@matchadating.it` in copia, copia salvata in Posta inviata, mail 2 e 3 nello stesso thread della mail 1 |
| Registra | Aggiorna il funnel e scrive ogni modifica (valore vecchio → nuovo) nel Doc "Matcha - Funnel Vendita - cronologia modifiche" |
| WhatsApp | Per i locali senza mail ma con cellulare apre WhatsApp con il messaggio già scritto: premi tu invia |

## Regole della sequenza

| Locale nel funnel | Azione |
|---|---|
| `10 - nuovo`, con mail, non "TODO: da visitare" | Mail 1, poi Mail 2 dopo 4 giorni lavorativi, poi Mail 3 (break up) dopo altri 6 |
| `10 - nuovo` che ha risposto | Esce dalla sequenza: in grigio "Ha risposto". La leggi tu o la legge Claude con `risposte` |
| "Ultima azione fatta" = `STOP` o Mail step `stop` | Mai più contattato, qualunque sia la Probabilità |
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

Per togliere a mano un locale dalla sequenza basta scrivere `stop` o `risposta` in "Mail step". Il comando `segna "Locale" stop` scrive `stop` in "Mail step", `STOP` (chip nero) in "Ultima azione fatta" e svuota "Mail prossimo invio"; `segna "Locale" risposta` chiude la sequenza senza toccare "Ultima azione fatta".

Nelle colonne già esistenti il mailer scrive:

| Colonna | Cosa scrive |
|---|---|
| Ultima azione fatta | `Email automatica 1`, `Email automatica 2`, `Email automatica 3 (break up)`, `Email automatica lettera d'intenti`, `WhatsApp automatico lettera d'intenti`, `STOP` (con `segna ... stop`). Sono nel menu a tendina della colonna insieme ai valori manuali (Di persona, Chiamata, Email, Instagram, Lettera firmata, TODO: da visitare) |
| Last contacted | Data dell'invio |
| Note | Dopo una virgola un frammento tipo "Email automatica 1 inviata il 12/10/2026", che sostituisce il frammento precedente del mailer senza toccare il resto della nota |

Se si cambiano questi valori nel codice (`LAST_ACTION_VALUE` in `planner.py`), vanno aggiunti anche al menu a tendina di "Ultima azione fatta", altrimenti il foglio li segna come non validi.

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
.venv\Scripts\python -m matcha_mailer risposte                       (legge le risposte, non le segna come lette)
.venv\Scripts\python -m matcha_mailer segna "Nome locale" stop --conferma (non vuole essere contattato)
.venv\Scripts\python -m matcha_mailer password                         (salva la password Aruba, solo tu)
```

## Installazione (una volta)

Chi fa cosa:

| Passo | Chi | Perché |
|---|---|---|
| 1. Ambiente `.venv` e librerie | Claude (o doppio clic su `Matcha Mailer.bat`) | Nessun dato riservato |
| 2. `config.ini` con gli ID dei file Drive | Claude, se ha accesso a Google Drive (cerca i file per titolo) | Gli ID non vanno nel repo pubblico, solo in `config.ini` |
| 3. Client OAuth Google (`secrets\credentials.json`) | Jacopo, guidato da Claude passo passo | Serve accedere a Google Cloud con il tuo account, accettare i termini e scaricare un segreto: Claude non lo fa |
| 4. Password Aruba nel portachiavi | Jacopo, digitandola in un terminale (Claude può aprirlo con il comando già pronto) | Claude non legge né digita password |
| 5. Primo accesso Google | Claude lancia il comando, Jacopo accede nel browser che si apre | L'accesso con password lo fa solo Jacopo |

### 1. Ambiente

Doppio clic su `Matcha Mailer.bat` oppure:

```
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

### 2. File di configurazione

Al primo avvio il mailer crea `config.ini` da `config.example.ini`. Completa gli ID dei tre file Drive (la parte dell'URL tra `/d/` e `/edit`): "Matcha - Funnel Vendita" (foglio `Sheet1`), "Matcha - Funnel Vendita - cronologia modifiche", "lettera_intenti_v2". `config.ini` non va su GitHub.

### 3. Accesso a Google: client OAuth

Si fa una volta sola, con **il tuo account Google personale** (quello che vede funnel, cronologia e lettera). Circa 10 minuti.

1. **Accesso.** Apri [console.cloud.google.com](https://console.cloud.google.com) e accedi con quell'account. Se è la prima volta, scegli Italia come paese e accetta i termini di servizio.
2. **Progetto.** In alto a sinistra clic sul selettore dei progetti → **Nuovo progetto**. Nome `Matcha Mailer`, Organizzazione "Nessuna organizzazione" → **Crea**. Quando è pronto, selezionalo dal selettore (il nome deve comparire in alto).
3. **API.** Apri questi tre link e su ciascuno clic su **Abilita** (controlla che in alto ci sia il progetto Matcha Mailer):
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com)
   - [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
4. **Schermata di consenso.** Apri [Google Auth Platform](https://console.cloud.google.com/auth/overview) → **Inizia** e compila:
   - Informazioni sull'app: nome `Matcha Mailer`, email di assistenza: il tuo indirizzo → Avanti;
   - Pubblico: **Esterno** → Avanti;
   - Dati di contatto: il tuo indirizzo → Avanti;
   - accetta le norme sui dati utente → **Crea**.
5. **Utente di test.** Menu a sinistra **Pubblico** → sezione "Utenti di test" → **Aggiungi utenti** → il tuo indirizzo → **Salva**. Lascia lo stato di pubblicazione su "Test".
6. **Client.** Menu a sinistra **Client** → **Crea client** → Tipo di applicazione **App desktop**, nome `Matcha Mailer` → **Crea**. Nella finestra che si apre clic su **Scarica JSON** subito: il segreto si vede solo ora. Se la chiudi per errore, elimina il client e creane un altro.
7. **File.** Il file scaricato si chiama `client_secret_....json` ed è in Download oppure sul Desktop (dipende dal browser): se il comando non lo trova, sostituisci `Downloads` con `Desktop`. Spostalo nella cartella del mailer come `secrets\credentials.json`, ad esempio da PowerShell nella cartella del mailer:

   ```
   New-Item -ItemType Directory -Force secrets
   Move-Item "$env:USERPROFILE\Downloads\client_secret_*.json" secrets\credentials.json
   ```

8. **Verifica.** `.venv\Scripts\python -m matcha_mailer verifica` deve dire `OK  secrets/credentials.json`.

### 4. Password Aruba

Il mailer salva la password di `jacopo@matchadating.it` nel portachiavi di Windows (Gestione credenziali), non in un file. In un terminale nella cartella del mailer:

```
.venv\Scripts\python -m matcha_mailer password
```

Digita la password (non compare mentre scrivi) e premi Invio: il mailer la prova con Aruba e risponde "Password verificata con Aruba e salvata nel portachiavi di Windows". Se la cambi, rifai questo passo.

### 5. Primo accesso Google

Al primo comando che legge il funnel (`verifica` o `stato`) si apre il browser:

1. scegli il tuo account Google personale;
2. alla schermata "Google non ha verificato questa app" clic su **Avanzate** → **Vai a Matcha Mailer (non sicura)**: è la tua app;
3. spunta tutti gli accessi richiesti (Fogli, Documenti, Drive in sola lettura) → **Continua**;
4. quando il browser dice che l'autenticazione è completata, chiudi la scheda.

Il mailer salva il token in `secrets\token.json`. Con l'app in modalità test Google chiede di rifare l'accesso ogni 7 giorni: il mailer riapre il browser da solo.

### 6. Collegamento sul desktop (facoltativo)

Tasto destro su `Matcha Mailer.bat` → Invia a → Desktop (crea collegamento).

### 7. Lettera d'intenti

Per il link nel WhatsApp, `lettera_intenti_v2` deve essere condivisa in sola lettura con "Chiunque abbia il link".

## DNS di matchadating.it

SPF, DKIM e DMARC sono già configurati (record su Vercel, ottobre 2026). Valori di riferimento, se le mail iniziano a finire in spam:

| Record | Nome | Valore |
|---|---|---|
| SPF (TXT) | `@` | `v=spf1 include:_spf.aruba.it -all` |
| DKIM (TXT) | quello indicato da Aruba | record copiato dal pannello Aruba |
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
  mailbox.py           SMTP, copia in Inviati, controllo e lettura risposte IMAP
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
