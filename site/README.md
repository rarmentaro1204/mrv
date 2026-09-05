# Preventivatore MRV — sorgente del sito

`index.html` è il file sorgente pubblicato su **preventivomrv.netlify.app**
(configuratore di preventivi a marchio MRV Consulting, con backend Google
Sheets condiviso — vedi `../scripts/google-apps-script/`).

## Come funziona il deploy

Al momento il deploy su Netlify è **manuale**: quando il file viene
aggiornato, va ricaricato a mano su Netlify (drag & drop di `index.html`
nella dashboard del sito, o `netlify deploy --prod` da CLI).

Per un deploy automatico ad ogni modifica, basta collegare il sito Netlify
a questa repo GitHub (Netlify → Site settings → Build & deploy → Link
repository), impostando come **publish directory** `site` — da quel
momento ogni push su questo branch/`main` pubblica in automatico
`site/index.html` senza bisogno di caricarlo a mano.

## Nota sul token del backend

`index.html` contiene, in chiaro nel codice JavaScript lato client, l'URL
e il token del backend Google Sheets (`scripts/google-apps-script/`).
Essendo un sito statico, questo token è comunque visibile a chiunque apra
gli strumenti sviluppatore del browser sul sito pubblicato — non è un
segreto "vero", ma un tornello contro l'uso casuale/accidentale
dell'endpoint, non contro un attacco mirato (vedi la sezione "Sicurezza"
in `../scripts/google-apps-script/README.md`).
