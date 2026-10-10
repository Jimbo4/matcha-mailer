# Matcha · Testi outreach locali (bozza da revisionare)

Mittente: jacopo@matchadating.it · CC: info@matchadating.it · Registro: tu
Le parole tra graffe `{...}` le riempie lo script (vedi tabella in fondo).

Il mailer legge questo file a ogni avvio: puoi cambiare i testi qui. Per non romperlo:

- non rinominare i titoli `## Firma`, `## Mail 1 ·`, `## Mail 2 ·`, `## Mail 3 ·`, `## Mail 4 ·`, `## WhatsApp ·`;
- tieni le righe `- **Oggetto:**`, `- **Quando:**`, `- **Allegato:**` subito sotto il titolo;
- chiudi ogni sezione con una riga `---`;
- le mail 2 e 3 partono in risposta alla mail 1, con oggetto "Re: " + oggetto della mail 1;
- la firma va dopo il saluto e prima dell'eventuale PS: la aggiunge il mailer.

---

## Firma

### HTML (webmail Aruba e script)

```html
<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;font-family:'DM Sans',Helvetica,Arial,sans-serif;font-size:13px;line-height:20px;">
<tr><td style="padding:0;">
<b>Jacopo Marcolini</b><span style="color:#38A096;">&nbsp;|&nbsp;</span>CMO &amp; Co-founder<span style="color:#38A096;">&nbsp;|&nbsp;</span><span style="font-family:'Fraunces',Georgia,'Times New Roman',serif;font-weight:900;font-size:15px;color:#38A096;">Matcha</span>
</td></tr>
<tr><td style="padding:4px 0 0 0;">
tel: +39 345 859 1948<span style="color:#38A096;">&nbsp;|&nbsp;</span>sito: <a href="https://www.matchadating.it" style="color:inherit;text-decoration:underline;">matchadating.it</a><span style="color:#38A096;">&nbsp;|&nbsp;</span>ig: <a href="https://www.instagram.com/matchadating_it/" style="color:inherit;text-decoration:underline;">@matchadating_it</a>
</td></tr>
</table>
```

### Testo semplice (app Gmail)

```text
Jacopo Marcolini | CMO & Co-founder | Matcha
tel: +39 345 859 1948 | sito: matchadating.it | ig: instagram.com/matchadating_it
```

---

## Mail 1 · Primo contatto a freddo

- **Quando:** giorno 0, nuovo thread
- **Oggetto:** Partnership {nome_locale} x Matcha

Ciao {nome},
sono Jacopo, co-founder di Matcha: con la nostra start-up vogliamo spingere le persone a incontrarsi di nuovo dal vivo, collaborando con i locali milanesi per portare prenotazioni e nuovi clienti. Matcha è una dating app senza chat: dopo essersi scelti, ci si incontra direttamente per un drink in un locale partner.

A Milano hanno già aderito {n_locali} locali e {nome_locale} ci sembra proprio il posto giusto per un primo appuntamento!

Come funziona per voi:
- ogni persona paga 10€ in app prima dell'appuntamento: 6€ a persona (12€ a coppia) vanno a voi, per una consumazione che proponete voi da una lista ristretta (solitamente una birra piccola o uno spritz);
- nessun costo di adesione;
- tutto quello che ordinano dopo il primo drink resta a voi.

Ti va di conoscerci?
Posso passare di persona 15 minuti quando ti è comodo, oppure ci sentiamo al telefono.

Jacopo

PS: se non vuoi più essere contattato da noi di Matcha, rispondi "stop" (ma sappi che mi spezzerai il cuore 💔).

---

## Mail 2 · Follow up

- **Quando:** +4 giorni lavorativi dalla mail 1, in risposta alla mail 1 (stesso thread)

Ciao {nome},
abbiamo alcuni appuntamenti su Matcha che aspettano un locale in cui incontrarsi. Possiamo sentirci 15 minuti {domani} pomeriggio per parlarne?

Ti ricordo come funziona per voi:
- ogni coppia paga 20€ in app prima dell'appuntamento: 12€ vanno a voi, per due consumazioni che proponete voi da una lista ristretta;
- nessun costo di adesione;
- tutto quello che ordinano dopo il primo drink resta a voi.

Jacopo

PS: se non vuoi più essere contattato da noi di Matcha, rispondi "stop" (ma sappi che mi spezzerai il cuore 💔).

---

## Mail 3 · Break up

- **Quando:** +6 giorni lavorativi dalla mail 2, in risposta alla mail 1 (stesso thread)

Ciao {nome},
non avendo avuto tue notizie, immagino che Matcha non sia una priorità per {nome_locale} in questo momento. Nessun problema, questa è la mia ultima mail.

Abbiamo {numero_coppie} coppie in attesa di incontrarsi nei locali partner in zona {zona}. Mi sarebbe piaciuto che uno di questi fosse {nome_locale}.

Se cambi idea, rispondi a questa mail e ti ricontatto io.

A presto,
Jacopo

---

## Mail 4 · Dopo visita o chiamata

- **Quando:** dopo una visita o una telefonata con esito "interessato" senza firma
- **Oggetto:** Lettera d'intenti {nome_locale} x Matcha
- **Allegato:** lettera d'intenti (PDF)

Ciao {nome},
sono Jacopo, co-founder di Matcha, l'app di incontri per riportare le persone a conoscersi dal vivo: grazie ancora per il tempo che ci hai dedicato {quando_ci_siamo_sentiti}.

Ti allego la lettera d'intenti, così ce l'hai sottomano. Non vincola nessuna delle due parti e ci serve per inserire {nome_locale} tra i locali partner da tenere in considerazione.

Se sei interessato, possiamo proseguire così:
1. firma la lettera e rispondimi con una foto o con il PDF;
2. se prima vuoi chiarire qualche dubbio, mandami un numero e un orario e ti chiamo io.

A presto,
Jacopo

---

## WhatsApp · Dopo visita

- **Quando:** come la mail 4, per i locali senza mail ma con un cellulare

Ciao {nome}, sono Jacopo di Matcha, l'app di incontri dal vivo: grazie ancora per il tempo che ci hai dedicato {quando_ci_siamo_sentiti}. Ecco la lettera d'intenti: {link_pdf}. Se ti va, firmala e mandami una foto qui. Se prima vuoi chiarire qualcosa, dimmi quando posso chiamarti. Grazie!

---

## Variabili

| Variabile | Da dove arriva | Se manca |
|---|---|---|
| `{nome}` | Colonna "Referente" del funnel (solo il nome) | "Ciao," senza nome |
| `{nome_locale}` | Colonna "Nome attività" | Sempre presente |
| `{zona}` | Colonna "Zona" | "nei locali partner della tua zona" |
| `{n_locali}` | Conteggio righe "90 - firmato intento" (oggi 4) | Da scrivere a mano in anteprima |
| `{domani}` | "domani" se il giorno dopo l'invio è lavorativo, altrimenti il giorno (es. "lunedì") | Sempre calcolato |
| `{quando_ci_siamo_sentiti}` | "Ultima azione fatta" + "Last contacted": "da {nome_locale} il 28/09" (visita) oppure "al telefono" (chiamata) | "da {nome_locale} nei giorni scorsi" |
| `{link_pdf}` | Link di download PDF di lettera_intenti_v2 (serve la condivisione "chiunque abbia il link") | Sempre presente |
| `{numero_coppie}` | Lo scrivi tu nell'anteprima della mail 3 | La mail non parte finché manca |
