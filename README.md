# Matcha Mailer

Mailer semi-automatico per contattare i locali partner di [Matcha](https://www.matchadating.it). Parte dal funnel su Google Sheets, invia da `jacopo@matchadating.it` (Aruba), aggiorna il funnel e scrive ogni modifica nel Doc di cronologia. Nessuna mail parte senza il tuo ok.

## Come si usa

| Modo | Quando | Come |
|---|---|---|
| Claude dall'app, collegato al PC | Il modo abituale | Chiedi a Claude cosa fare. Claude prepara una **richiesta**, tu fai doppio clic su **Esegui richiesta.bat** e gli scrivi "fatto" |
| Claude Code aperto nella cartella | Lavori al PC con Claude Code | Claude lancia direttamente i comandi |
| Terminale | Vuoi fare da solo | `.venv\Scripts\python -m matcha_mailer <comando>` dalla cartella del mailer |

### Le richieste di Claude

Dall'app Claude vede e modifica i file della cartella, ma non può avviare il mailer: la password Aruba è nel portachiavi di Windows e il controllo del PC non gli permette di scrivere nei terminali. Per questo:

1. Claude scrive i comandi in `locale\richieste\da_eseguire.txt` e ti dice cosa faranno;
2. tu fai doppio clic su **Esegui richiesta.bat**: la finestra elenca i comandi e, se qualcuno invia mail o modifica il funnel, procede solo se scrivi `SI`;
3. l'esito resta in `locale\esiti\AAAAMMGG-HHMM_titolo.txt` e la richiesta passa in `locale\richieste\eseguite\`, così non può ripartire per sbaglio;
4. scrivi "fatto" a Claude, che legge l'esito e ti risponde.

Gli invii seguono sempre due passaggi: prima una richiesta con l'anteprima, poi, dopo il tuo ok, quella che invia.

## Comandi

| Comando | Cosa fa | Modifica qualcosa? |
|---|---|---|
| `verifica` | Controlla configurazione, credenziali, funnel e Aruba | No |
| `stato` | Azioni da fare oggi e locali in attesa | No |
| `candidati` | Locali a Milano con mail e Probabilità vuota, pronti da inserire nella sequenza (`--zona`, `--anche-fuori-milano`) | No |
| `attiva "Locale" ...` | Mette Probabilità `10 - nuovo`, poi rilegge il funnel e scrive la cronologia | Sì, con `--conferma` |
| `anteprima "Locale"` | Destinatari, oggetto e testo con firma | No |
| `prova "Locale"` | Manda la mail solo a te, con "[PROVA]" nell'oggetto | Solo una mail a te |
| `invia "Locale" ...` | Senza `--conferma` mostra le anteprime e non invia | Sì, con `--conferma` |
| `whatsapp "Locale"` | Testo e link WhatsApp pronti; `--inviato` registra l'invio | Sì, con `--inviato` |
| `risposte` | Legge le risposte dei locali già scritti, senza segnarle come lette | No |
| `casella` | Legge tutta la casella dal primo invio e classifica le mail: stop, segnalazioni spam, rimbalzi, risposte vere e automatiche, report DMARC. Legge solo intestazioni e inizio del testo, mai gli allegati | No |
| `segna "Locale" stop` / `risposta` | Chiude la sequenza del locale | Sì, con `--conferma` |
| `richiesta` | Esegue `locale\richieste\da_eseguire.txt` (è ciò che fa Esegui richiesta.bat) | Dipende dai comandi |
| `password` | Salva la password Aruba (doppio clic su **Salva password Aruba.bat**) | Solo il portachiavi |

Opzioni di `anteprima`, `prova` e `invia`:

| Opzione | Uso |
|---|---|
| `--nome "Nome nel funnel=Nome nella mail"` | Nome breve del locale in oggetto e testo (es. `"Enoteca Esempio (Sede Isola)=Enoteca Esempio"`). Il mailer lo ricorda e lo riusa in Mail 2 e Mail 3, nello stesso thread |
| `--valore nome=valore` | Completa una parte tra graffe, es. `--valore numero_coppie=12` |
| `--oggetto "..."`, `--testo-file locale/bozze/x.txt` | Oggetto e testo scritti a mano per **un solo** locale; la firma si aggiunge da sola |
| `--riattiva` | Scrive a un locale `00 - perso` indicato, su tua richiesta |
| `--oltre-soglia` (solo `invia`) | Supera la soglia settimanale, solo con il tuo ok |

## Regole della sequenza

| Locale nel funnel | Azione |
|---|---|
| Mail presente, Probabilità vuota | Candidato: entra nella sequenza con `attiva` |
| `10 - nuovo`, con mail, non "TODO: da visitare" | Mail 1, poi Mail 2 dopo 4 giorni lavorativi, poi Mail 3 (break up) dopo altri 6, tutte nello stesso thread |
| `10 - nuovo` che ha risposto | Esce dalla sequenza ("Ha risposto"): la leggi tu o Claude con `risposte`. Le risposte automatiche ("vi risponderemo al più presto", fuori ufficio) non contano: la sequenza prosegue e `stato` lo segnala |
| "Ultima azione fatta" = `STOP` o Mail step `stop` | Mai più contattato, qualunque sia la Probabilità |
| Ha segnalato una mail come spam | Come chi scrive "stop": `segna "Locale" stop` |
| `50 - curioso` con mail | Mail 4 con la lettera d'intenti in PDF (esportata dal Doc a ogni invio) |
| `50 - curioso` senza mail, con cellulare | WhatsApp con link alla lettera |
| `50 - curioso` con solo numero fisso | Da chiamare |
| `00 - perso` con mail, su tua richiesta (`--riattiva`) | Come `10 - nuovo`; la Probabilità resta `00` |
| `90`, `00` senza richiesta, "TODO: da visitare" | Nessuna azione |

- I giorni lavorativi escludono weekend, festività nazionali, Pasquetta e Sant'Ambrogio.
- Oltre 20 mail a settimana il mailer chiede `--oltre-soglia`.
- Tra un invio e l'altro fa una pausa casuale di 5-30 secondi. Se Aruba chiude la connessione prima dell'invio, riprova due volte (dopo 20 e 40 secondi).
- Se l'errore arriva durante la consegna non riprova: la mail potrebbe essere partita, quindi va controllata la copia in Cc.
- Soglia e pause si cambiano in `locale\config.ini`.
- Il controllo delle risposte ignora le mail che partono da jacopo@: le copie dei nostri follow up arrivano in casella tramite il Cc a info@ e non vanno scambiate per risposte.
- Quando un locale non ha azioni, il mailer spiega il motivo e cosa fare.

### Colonne del funnel

| Colonna | Cosa scrive il mailer |
|---|---|
| Mail step | vuoto = mai scritto · `1` `2` `3` = mail della sequenza · `4` = lettera · `WA` = WhatsApp · `stop` · `risposta` |
| Mail ultimo invio / Mail prossimo invio | Date dell'ultimo invio e della mail successiva |
| Mail thread | Identificativo tecnico della Mail 1, serve a tenere il thread |
| Probabilitá | `10 - nuovo` con `attiva` |
| Ultima azione fatta | `Email automatica 1`/`2`/`3 (break up)`, `Email automatica lettera d'intenti`, `WhatsApp automatico lettera d'intenti`, `STOP`: sono nel menu a tendina della colonna. Se si cambiano in `planner.py` (`LAST_ACTION_VALUE`), vanno aggiunti anche al menu |
| Last contacted | Data dell'invio |
| Note | Dopo una virgola un frammento tipo "Email automatica 1 inviata il 12/10/2026", che sostituisce il frammento precedente del mailer |

Per togliere a mano un locale dalla sequenza basta scrivere `stop` o `risposta` in "Mail step".

## Cartella

```
matcha-mailer/
  Esegui richiesta.bat       esegue la richiesta preparata da Claude (la prima volta installa le librerie)
  Salva password Aruba.bat   salva la password di jacopo@matchadating.it nel portachiavi di Windows
  README.md                  questo file (per te)
  CLAUDE.md                  istruzioni e regole per Claude
  testi_email.md             testi di mail, WhatsApp e firma
  config.example.ini         modello di locale/config.ini
  matcha_mailer/             codice
  tests/                     test (dati inventati)
  locale/                    tutto ciò che è di questo PC: non va su GitHub
    config.ini               mittente, server Aruba, ID dei file Drive, sequenza, soglia, pause
    segreti/                 credenziali e token Google (non aprire, non copiare)
    registro/invii.csv       ogni mail o WhatsApp partito (data, locale, oggetto, Message-ID, nome usato)
    richieste/               da_eseguire.txt e, in eseguite/, quelle già eseguite
    esiti/                   AAAAMMGG-HHMM_titolo.txt, uno per richiesta
    bozze/                   testi modificati a mano per --testo-file
    archivio/                file vecchi, da tenere ma non più usati
```

### Codice

| File | Ruolo |
|---|---|
| `cli.py` | Comandi: legge gli argomenti, chiama le operazioni, stampa |
| `richieste.py` | Esegue le richieste di Claude e salva l'esito |
| `operazioni.py` | Le operazioni: piano del giorno, invio, attivazione, casella. Collega i moduli sotto |
| `planner.py` | Regole della sequenza e spiegazioni (senza rete) |
| `testi.py`, `calendario.py` | Testi da `testi_email.md`, giorni lavorativi (senza rete) |
| `funnel.py` | Foglio Google: colonne per nome, righe per nome del locale |
| `cronologia.py` | Doc di cronologia: valore vecchio → nuovo per ogni modifica |
| `casella.py` | Aruba: invio SMTP con secondo tentativo, Posta inviata, lettura e classificazione delle mail |
| `registro.py` | `locale/registro/invii.csv` |
| `google_api.py`, `portachiavi.py`, `config.py` | Accesso Google, password Aruba, percorsi e configurazione |

## Installazione (una volta)

| Passo | Chi | Come |
|---|---|---|
| 1. Ambiente e librerie | Jacopo | Doppio clic su **Esegui richiesta.bat** (la prima volta crea `.venv` e installa tutto) |
| 2. `locale/config.ini` | Claude, se ha Google Drive | Il mailer lo crea dal modello; vanno inseriti gli ID di "Matcha - Funnel Vendita" (foglio `Sheet1`), "Matcha - Funnel Vendita - cronologia modifiche" e "lettera_intenti_v2" (la parte dell'URL tra `/d/` e `/edit`) |
| 3. Client OAuth Google | Jacopo, guidato da Claude | Vedi sotto: accesso a Google Cloud con il tuo account e download di un segreto |
| 4. Password Aruba | Jacopo | Doppio clic su **Salva password Aruba.bat** e digiti la password |
| 5. Primo accesso Google | Claude prepara una richiesta con `verifica`, Jacopo accede nel browser che si apre | Account personale → "Avanzate" → "Vai a Matcha Mailer (non sicura)" → spunta tutti gli accessi |

### Accesso a Google: client OAuth

Si fa una volta sola, con **il tuo account Google personale** (quello che vede funnel, cronologia e lettera). Circa 10 minuti.

1. **Accesso.** Apri [console.cloud.google.com](https://console.cloud.google.com) e accedi con quell'account. Se è la prima volta, scegli Italia come paese e accetta i termini di servizio.
2. **Progetto.** In alto a sinistra clic sul selettore dei progetti → **Nuovo progetto**. Nome `Matcha Mailer`, Organizzazione "Nessuna organizzazione" → **Crea**. Quando è pronto, selezionalo dal selettore.
3. **API.** Apri questi tre link e su ciascuno clic su **Abilita** (in alto deve esserci il progetto Matcha Mailer):
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com)
   - [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
4. **Schermata di consenso.** Apri [Google Auth Platform](https://console.cloud.google.com/auth/overview) → **Inizia**: nome `Matcha Mailer` e il tuo indirizzo come email di assistenza → Avanti; Pubblico **Esterno** → Avanti; il tuo indirizzo nei dati di contatto → Avanti; accetta le norme → **Crea**.
5. **Utente di test.** Menu **Pubblico** → "Utenti di test" → **Aggiungi utenti** → il tuo indirizzo → **Salva**. Lascia lo stato su "Test".
6. **Client.** Menu **Client** → **Crea client** → **App desktop**, nome `Matcha Mailer` → **Crea** → **Scarica JSON** subito (il segreto si vede solo ora; se chiudi la finestra, elimina il client e creane un altro).
7. **File.** Sposta il file `client_secret_....json` (in Download o sul Desktop) nella cartella del mailer come `locale\segreti\credentials.json`, ad esempio da PowerShell nella cartella del mailer:

   ```
   New-Item -ItemType Directory -Force locale\segreti
   Move-Item "$env:USERPROFILE\Downloads\client_secret_*.json" locale\segreti\credentials.json
   ```

8. **Verifica.** `verifica` deve dire `OK  locale/segreti/credentials.json`.

Con l'app in modalità test Google chiede di rifare l'accesso ogni 7 giorni: si apre il browser da solo. Per il link nel WhatsApp, `lettera_intenti_v2` deve essere condivisa in sola lettura con "Chiunque abbia il link".

## DNS di matchadating.it

SPF, DKIM e DMARC sono già configurati (record su Vercel, ottobre 2026). Valori di riferimento, se le mail iniziano a finire in spam:

| Record | Nome | Valore |
|---|---|---|
| SPF (TXT) | `@` | `v=spf1 include:_spf.aruba.it -all` |
| DKIM (TXT) | quello indicato da Aruba | record copiato dal pannello Aruba |
| DMARC (TXT) | `_dmarc` | `v=DMARC1; p=none; rua=mailto:info@matchadating.it` |

Ogni giorno arrivano a info@matchadating.it (e quindi anche nella casella di jacopo@) i report DMARC aggregati, per via di `rua`: oggetto tipo "Report domain: matchadating.it Submitter: google.com" (oppure Microsoft, Yahoo), con allegato .zip o .gz. Non sono segnalazioni di spam: dicono solo quante mail del dominio hanno superato SPF e DKIM, senza destinatari né locali. Il comando `casella` li tiene separati dalle richieste di stop e dalle segnalazioni vere.

## Modificare i testi

Tutti i testi, firma compresa, sono in [`testi_email.md`](testi_email.md): il mailer lo rilegge a ogni comando. In cima al file ci sono le regole per non romperlo.

## Sviluppo

- Test: `.venv\Scripts\python -m pip install pytest`, poi `.venv\Scripts\python -m pytest`. I dati di test sono inventati: nel repo non vanno nomi, mail o telefoni reali dei locali.
- Ogni modifica al comportamento va coperta da un test e descritta qui.
- `locale/`, i PDF e le vecchie posizioni (`config.ini`, `secrets/`, `data/`) sono esclusi da `.gitignore`.
