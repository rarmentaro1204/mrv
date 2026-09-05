# Backend Google Sheets per MRV Preventivi

Il preventivatore (artifact Claude o versione self-hosted su Netlify) può
usare un Google Sheet come database condiviso tra soci: numerazione
progressiva, cronologia preventivi salvati, intestazione/footer aziendali.

Dentro l'anteprima Claude il tool usa comunque il proprio database interno
(più semplice, zero setup). **Il backend Google Sheets serve per la versione
self-hosted** (il file HTML autonomo, es. su Netlify), dove non esiste un
database condiviso automatico.

## Setup (una tantum, ~5 minuti)

1. Crea un nuovo **Google Sheet** (vuoto va bene: fogli e intestazioni
   colonna vengono creati automaticamente al primo utilizzo).
2. Menu **Estensioni → Apps Script**.
3. Cancella il contenuto di default e incolla tutto il contenuto di
   [`Code.gs`](./Code.gs).
4. In cima al file, sostituisci
   ```js
   const API_TOKEN = 'CAMBIA_QUESTO_TOKEN_SEGRETO';
   ```
   con una stringa segreta a tua scelta (es. una password lunga generata a
   caso). Serve perché la web app finale è pubblica: senza token chiunque
   trovi l'URL potrebbe leggere/scrivere i preventivi.
5. **Distribuisci → Nuova implementazione**:
   - Tipo: **App web**
   - Esegui come: **Me**
   - Chi ha accesso: **Chiunque** (non "Chiunque abbia un Account Google" —
     il preventivatore chiama l'URL senza login)
6. Autorizza l'app quando richiesto (è normale l'avviso "app non
   verificata": è uno script tuo, su un tuo foglio).
7. Copia l'**URL dell'app web** (finisce con `/exec`).
8. Comunica a chi ha configurato il preventivatore **l'URL** e **il token**
   scelto al passo 4: vanno incollati come `SHEETS_API_URL` e
   `SHEETS_API_TOKEN` in cima allo script del file HTML del preventivatore.

## Aggiornare lo script in futuro

Ogni volta che modifichi `Code.gs` nell'editor Apps Script, le modifiche
**non** si applicano automaticamente all'URL già distribuito: devi andare in
**Distribuisci → Gestisci implementazioni → Modifica (icona matita) →
Nuova versione → Distribuisci**.

## Struttura del foglio (creata automaticamente)

- **Preventivi** — una riga per preventivo salvato (id, numero, cliente,
  righe e totali in JSON, date, timestamp).
- **Contatore** — un rigo per anno con il prossimo numero progressivo da
  assegnare.
- **Impostazioni** — coppia chiave/valore, contiene la riga `company` con
  il JSON di intestazione/footer aziendali condivisi tra tutti i soci.

Puoi aprire il foglio in qualsiasi momento per consultare/esportare i
preventivi con gli strumenti normali di Google Sheets (filtri, grafici,
esportazione Excel...).

## Sicurezza

L'endpoint è pubblico ma protetto solo da un token condiviso nell'URL/body
delle richieste — non è un sistema di autenticazione vero. È adeguato per
un tool interno a un piccolo team, non per dati sensibili di terzi. Se in
futuro serve un controllo più solido, si può sostituire con un vero backend
con autenticazione.
