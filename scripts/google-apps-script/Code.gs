/**
 * Backend "MRV Preventivi" su Google Sheets.
 *
 * Espone il foglio Google collegato come piccola API REST-like, usata dal
 * preventivatore (versione self-hosted, fuori da Claude) per condividere tra
 * i soci: numerazione progressiva dei preventivi, cronologia preventivi
 * salvati, dati aziendali (intestazione/footer).
 *
 * SETUP (una tantum):
 * 1. Crea un nuovo Google Sheet (vuoto va bene, i fogli/intestazioni
 *    vengono creati automaticamente al primo utilizzo).
 * 2. Estensioni → Apps Script. Cancella il contenuto di default e incolla
 *    questo intero file.
 * 3. Sostituisci API_TOKEN qui sotto con una stringa segreta a tua scelta
 *    (es. una password lunga e casuale) — serve a evitare che chiunque
 *    trovi l'URL possa leggere/scrivere i dati.
 * 4. Distribuisci → Nuova implementazione → tipo "App web".
 *    - Esegui come: Me
 *    - Chi ha accesso: Chiunque
 *    (Deve essere "Chiunque", non "Chiunque abbia un Account Google":
 *    il preventivatore chiama l'URL senza login.)
 * 5. Copia l'URL "App web" (finisce con /exec) e comunicalo a chi ha
 *    configurato il preventivatore: va incollato come SHEETS_API_URL
 *    nel file HTML, insieme allo stesso API_TOKEN scelto sopra.
 * 6. Ogni volta che modifichi questo script, devi ripubblicare la
 *    distribuzione (Distribuisci → Gestisci implementazioni → Modifica →
 *    Nuova versione) perché le modifiche abbiano effetto sull'URL esistente.
 */

const API_TOKEN = 'CAMBIA_QUESTO_TOKEN_SEGRETO'; // <-- imposta una tua stringa segreta

const SHEET_NAMES = { QUOTES: 'Preventivi', COUNTER: 'Contatore', SETTINGS: 'Impostazioni' };
const QUOTE_HEADERS = ['id', 'number', 'dataEmissione', 'dataValidita', 'clienteJson', 'righeJson', 'note', 'regimeIva', 'totalsJson', 'createdAt', 'updatedAt'];

function doGet(e) { return handle(e); }
function doPost(e) { return handle(e); }

function handle(e) {
  try {
    const params = (e && e.parameter) || {};
    let body = {};
    if (e && e.postData && e.postData.contents) {
      try { body = JSON.parse(e.postData.contents); } catch (err) { body = {}; }
    }
    const action = body.action || params.action;
    const token = body.token || params.token;
    if (token !== API_TOKEN) {
      return jsonOutput({ ok: false, error: 'Token non valido' });
    }

    let result;
    switch (action) {
      case 'nextNumber': result = nextNumber(body.year || params.year); break;
      case 'saveQuote': result = saveQuote(body.quote); break;
      case 'listQuotes': result = listQuotes(); break;
      case 'deleteQuote': result = deleteQuote(body.id || params.id); break;
      case 'getSettings': result = getSettings(); break;
      case 'saveSettings': result = saveSettings(body.company); break;
      default: throw new Error('Azione non riconosciuta: ' + action);
    }
    return jsonOutput({ ok: true, result: result });
  } catch (err) {
    return jsonOutput({ ok: false, error: String((err && err.message) || err) });
  }
}

function jsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function getSheet(name, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    if (headers) sheet.appendRow(headers);
  }
  return sheet;
}

/* ---------------- Contatore (numerazione progressiva per anno) ---------------- */
function nextNumber(year) {
  year = String(year || new Date().getFullYear());
  const sheet = getSheet(SHEET_NAMES.COUNTER, ['Anno', 'ProssimoNumero']);
  const lock = LockService.getScriptLock();
  lock.waitLock(10000); // evita numeri duplicati se due persone salvano nello stesso istante
  try {
    const data = sheet.getDataRange().getValues();
    let rowIndex = -1;
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][0]) === year) { rowIndex = i; break; }
    }
    let seq;
    if (rowIndex === -1) {
      seq = 1;
      sheet.appendRow([year, 2]);
    } else {
      seq = Number(data[rowIndex][1]) || 1;
      sheet.getRange(rowIndex + 1, 2).setValue(seq + 1);
    }
    const padded = String(seq).padStart(4, '0');
    return { id: 'q-' + year + '-' + padded, number: 'n: ' + padded + '/' + year };
  } finally {
    lock.releaseLock();
  }
}

/* ---------------- Preventivi ---------------- */
function saveQuote(quote) {
  if (!quote || !quote.id) throw new Error('Preventivo non valido (id mancante)');
  const sheet = getSheet(SHEET_NAMES.QUOTES, QUOTE_HEADERS);
  const data = sheet.getDataRange().getValues();
  let rowIndex = -1;
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(quote.id)) { rowIndex = i; break; }
  }
  const now = new Date().toISOString();
  const row = [
    quote.id, quote.number, quote.dataEmissione, quote.dataValidita,
    JSON.stringify(quote.cliente || {}), JSON.stringify(quote.righe || []),
    quote.note || '', quote.regimeIva || 'forfettario', JSON.stringify(quote.totals || {}),
    quote.createdAt || now, now,
  ];
  if (rowIndex === -1) sheet.appendRow(row);
  else sheet.getRange(rowIndex + 1, 1, 1, row.length).setValues([row]);
  return { id: quote.id, updatedAt: now };
}

function listQuotes() {
  const sheet = getSheet(SHEET_NAMES.QUOTES, QUOTE_HEADERS);
  const data = sheet.getDataRange().getValues();
  const out = [];
  for (let i = 1; i < data.length; i++) {
    const r = data[i];
    if (!r[0]) continue;
    out.push({
      _id: r[0], number: r[1], dataEmissione: fmtDate(r[2]), dataValidita: fmtDate(r[3]),
      cliente: safeParse(r[4], {}), righe: safeParse(r[5], []),
      note: r[6], regimeIva: r[7], totals: safeParse(r[8], {}),
      createdAt: r[9], updatedAt: r[10],
    });
  }
  out.sort(function (a, b) { return String(b.updatedAt).localeCompare(String(a.updatedAt)); });
  return out;
}

function deleteQuote(id) {
  const sheet = getSheet(SHEET_NAMES.QUOTES, QUOTE_HEADERS);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(id)) { sheet.deleteRow(i + 1); break; }
  }
  return { id: id };
}

/* ---------------- Impostazioni azienda ---------------- */
function getSettings() {
  const sheet = getSheet(SHEET_NAMES.SETTINGS, ['Chiave', 'Valore']);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === 'company') return safeParse(data[i][1], {});
  }
  return {};
}

function saveSettings(company) {
  const sheet = getSheet(SHEET_NAMES.SETTINGS, ['Chiave', 'Valore']);
  const data = sheet.getDataRange().getValues();
  let rowIndex = -1;
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === 'company') { rowIndex = i; break; }
  }
  const value = JSON.stringify(company || {});
  if (rowIndex === -1) sheet.appendRow(['company', value]);
  else sheet.getRange(rowIndex + 1, 2).setValue(value);
  return { ok: true };
}

/* ---------------- Utility ---------------- */
function safeParse(s, fallback) {
  try { return s ? JSON.parse(s) : fallback; } catch (e) { return fallback; }
}
function fmtDate(v) {
  if (Object.prototype.toString.call(v) === '[object Date]') {
    return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  return v;
}
