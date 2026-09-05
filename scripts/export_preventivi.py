#!/usr/bin/env python3
"""
Sincronizza i preventivi salvati nel database dell'artifact "MRV Preventivi"
(https://claude.ai/code/artifact/e4e67e9c-5bfd-4b1e-a0bc-80d81d11a91f) nella
repo: genera un PDF di archivio per ogni preventivo nuovo o modificato e
aggiorna preventivi/registry.json e preventivi/counter.json.

Uso tipico (eseguito dalla routine di sincronizzazione):
  1. Con il tool Artifact, action=read_db, db_op=get, collection=settings,
     doc_id=company -> salvare il documento come JSON (es. /tmp/sync/company.json)
  2. Con il tool Artifact, action=read_db, db_op=query, collection=quotes,
     out_dir=/tmp/sync -> salva ogni preventivo come
     /tmp/sync/quotes/<id>.json
  3. Con il tool Artifact, action=read_db, db_op=get, collection=meta,
     doc_id=counter -> salvare come /tmp/sync/counter.json
  4. python3 scripts/export_preventivi.py \
       --company /tmp/sync/company.json \
       --quotes-dir /tmp/sync/quotes \
       --counter /tmp/sync/counter.json \
       --repo-root .

Il PDF generato qui è una copia di ARCHIVIO interna (font di sistema, nessuna
dipendenza di rete): il PDF "ufficiale" da mandare al cliente resta quello
generato dal preventivatore stesso (bottone "Genera PDF"), con i font di
brand caricati nel browser.

Richiede Playwright con Chromium già installato (ambiente Claude Code:
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers).
"""
import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TIPO_LABEL = {"una_tantum": "Una tantum", "mensile": "Mensile", "annuale": "Annuale"}


def eur(n):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.2f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"€ {s}"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def calc_totals(righe):
    tot = {"una_tantum": 0.0, "mensile": 0.0, "annuale": 0.0}
    for r in righe or []:
        prezzo = float(r.get("prezzo") or 0)
        qty = float(r.get("qty") or 0)
        tipo = r.get("tipo") if r.get("tipo") in tot else "una_tantum"
        tot[tipo] += prezzo * qty
    return tot


def righe_rows_html(righe):
    rows = []
    for r in righe or []:
        subtotale = float(r.get("prezzo") or 0) * float(r.get("qty") or 0)
        rows.append(f"""
        <tr>
          <td class="svc">
            <div class="svc-name">{esc(r.get('servizio'))}</div>
            <div class="svc-cat">{esc(r.get('categoria') or 'Personalizzato')}</div>
          </td>
          <td class="desc">{esc(r.get('descrizione'))}</td>
          <td class="tipo">{esc(TIPO_LABEL.get(r.get('tipo'), 'Una tantum'))}</td>
          <td class="num">{esc(r.get('qty') or 1)}</td>
          <td class="num">{esc(eur(r.get('prezzo')))}</td>
          <td class="num strong">{esc(eur(subtotale))}</td>
        </tr>""")
    return "".join(rows)


def totals_html(totals, regime):
    rows = []

    def line(label, value, suffix=""):
        if not value:
            return
        rows.append(f'<div class="trow"><span>{esc(label)}</span>'
                     f'<span class="v">{esc(eur(value))}{esc(suffix)}</span></div>')

    if regime == "esclusa":
        for label, key, suffix in (("Una tantum", "una_tantum", ""), ("Canone mensile", "mensile", "/mese"), ("Canone annuale", "annuale", "/anno")):
            v = totals.get(key, 0)
            if not v:
                continue
            line(f"{label} (imponibile)", v, suffix)
            line("  + IVA 22%", v * 0.22)
            line("  Totale", v * 1.22, suffix)
    elif regime == "inclusa":
        for label, key, suffix in (("Una tantum", "una_tantum", ""), ("Canone mensile", "mensile", "/mese"), ("Canone annuale", "annuale", "/anno")):
            v = totals.get(key, 0)
            if not v:
                continue
            line(f"{label} (tot. IVA inclusa)", v, suffix)
    else:
        line("Una tantum", totals.get("una_tantum", 0))
        line("Canone mensile", totals.get("mensile", 0), "/mese")
        line("Canone annuale", totals.get("annuale", 0), "/anno")

    if not rows:
        rows.append(f'<div class="trow"><span>Totale</span><span class="v">{esc(eur(0))}</span></div>')

    note = ("Operazione senza applicazione dell'IVA ai sensi dell'art. 1, commi 54-89, L. 190/2014 (regime forfettario)."
            if regime not in ("esclusa", "inclusa") else "Aliquota IVA applicata: 22%.")
    return "".join(rows), note


TEMPLATE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;background:#fff;color:#12161F;
    font-family:Georgia,'Times New Roman',serif}}
  .sheet{{padding:20mm 18mm;max-width:800px;margin:0 auto}}
  .head{{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}}
  .brand{{font-family:Georgia,serif;font-weight:700;font-size:28px;line-height:1}}
  .brand .dot{{color:#CBAA66}}
  .brand-sub{{font-family:Georgia,serif;font-style:italic;font-size:14px;margin-top:2px}}
  .issuer{{margin-top:12px;font-family:'Courier New',monospace;font-size:10.5px;color:#5B6472;line-height:1.7}}
  .meta{{text-align:right}}
  .eyebrow{{font-family:'Courier New',monospace;font-size:10px;letter-spacing:.25em;
    text-transform:uppercase;color:#8B7339;font-weight:700}}
  .docnum{{font-weight:700;font-size:20px;margin-top:4px}}
  .metarow{{font-family:'Courier New',monospace;font-size:11px;color:#5B6472;margin-top:6px}}
  .divider{{height:1px;background:#E2DECF;margin:22px 0}}
  h2.section{{font-family:'Courier New',monospace;font-size:10.5px;letter-spacing:.2em;
    text-transform:uppercase;color:#8B7339;margin:0 0 10px;font-weight:700}}
  .cliente{{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;font-size:13px}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{text-align:left;font-family:'Courier New',monospace;font-size:9.5px;letter-spacing:.1em;
    text-transform:uppercase;color:#8B7339;border-bottom:1px solid #E2DECF;padding:0 8px 8px}}
  td{{border-bottom:1px solid #E2DECF;padding:10px 8px;vertical-align:top}}
  .svc-name{{font-weight:700}}
  .svc-cat{{font-family:'Courier New',monospace;font-size:9px;color:#8A93A3;text-transform:uppercase;margin-top:2px}}
  .desc{{color:#4B5568;font-size:11.5px}}
  .num{{text-align:right;font-family:'Courier New',monospace;white-space:nowrap}}
  .strong{{font-weight:700}}
  .totals{{display:flex;justify-content:flex-end;margin-top:6px}}
  .totals-box{{width:300px;background:#F6F3EC;border-radius:10px;padding:16px 18px}}
  .trow{{display:flex;justify-content:space-between;font-family:'Courier New',monospace;
    font-size:11.5px;padding:4px 0;color:#4B5568}}
  .trow .v{{font-weight:700;color:#12161F}}
  .ivanote{{font-size:9.5px;color:#8A93A3;margin-top:8px;line-height:1.5}}
  .note{{white-space:pre-wrap;font-size:12px;color:#4B5568;line-height:1.7;border-top:1px solid #E2DECF;padding-top:12px}}
  .footer{{margin-top:30px;padding-top:14px;border-top:1px solid #E2DECF;text-align:center;
    font-family:'Courier New',monospace;font-size:9px;color:#8A93A3;white-space:pre-wrap;line-height:1.8}}
</style></head><body>
  <div class="sheet">
    <div class="head">
      <div>
        <div class="brand">MRV<span class="dot">.</span></div>
        <div class="brand-sub">Consulting</div>
        <div class="issuer">
          <strong>{titolare}</strong> — {forma}<br>
          {indirizzo}, {cap} {comune} ({provincia})<br>
          P.IVA {piva} · REA {rea}<br>
          {contatto}
        </div>
      </div>
      <div class="meta">
        <div class="eyebrow">Preventivo</div>
        <div class="docnum">{number}</div>
        <div class="metarow">Data: {dataEmissione}</div>
        <div class="metarow">Valido fino al: {dataValidita}</div>
      </div>
    </div>
    <div class="divider"></div>
    <h2 class="section">Cliente</h2>
    <div class="cliente">
      <div><strong>{cRagione}</strong></div>
      <div>{cPiva}</div>
      <div>{cIndirizzo}</div>
      <div>{cCitta}</div>
      <div>{cEmail}</div>
      <div>{cTelefono}</div>
    </div>
    <div class="divider"></div>
    <h2 class="section">Servizi</h2>
    <table>
      <thead><tr><th>Servizio</th><th>Descrizione</th><th>Tipo</th><th>Q.tà</th><th>Prezzo</th><th>Subtot.</th></tr></thead>
      <tbody>{righe_rows}</tbody>
    </table>
    <div class="totals"><div class="totals-box">{totals_rows}<div class="ivanote">{iva_note}</div></div></div>
    <div class="divider"></div>
    <h2 class="section">Note e condizioni</h2>
    <div class="note">{note}</div>
    <div class="footer">{footer}</div>
  </div>
</body></html>"""


def build_html(quote, company):
    c = quote.get("cliente") or {}
    totals = quote.get("totals") or calc_totals(quote.get("righe"))
    totals_rows, iva_note = totals_html(totals, quote.get("regimeIva"))
    contatto = " · ".join(filter(None, [
        f"PEC {company.get('pec')}" if company.get("pec") else "",
        company.get("email") or "",
    ])) or "—"
    footer = company.get("footerText") or "\n".join(filter(None, [
        f"{company.get('ragioneSociale','')} — {company.get('titolare','')}",
        f"P.IVA {company.get('piva','')} · REA {company.get('rea','')}",
        f"{company.get('indirizzo','')}, {company.get('cap','')} {company.get('comune','')} ({company.get('provincia','')})",
    ]))
    return TEMPLATE.format(
        titolare=esc(company.get("titolare")), forma=esc(company.get("formaGiuridica")),
        indirizzo=esc(company.get("indirizzo")), cap=esc(company.get("cap")),
        comune=esc(company.get("comune")), provincia=esc(company.get("provincia")),
        piva=esc(company.get("piva")), rea=esc(company.get("rea")), contatto=contatto,
        number=esc(quote.get("number") or "BOZZA"),
        dataEmissione=esc(quote.get("dataEmissione")), dataValidita=esc(quote.get("dataValidita")),
        cRagione=esc(c.get("ragione")), cPiva=esc(c.get("piva")),
        cIndirizzo=esc(c.get("indirizzo")), cCitta=esc(c.get("citta")),
        cEmail=esc(c.get("email")), cTelefono=esc(c.get("telefono")),
        righe_rows=righe_rows_html(quote.get("righe")),
        totals_rows=totals_rows, iva_note=esc(iva_note),
        note=esc(quote.get("note")), footer=esc(footer),
    )


def render_pdf(html_str, out_path):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_str, wait_until="load")
        page.pdf(path=str(out_path), format="A4", margin={"top": "12mm", "bottom": "12mm", "left": "14mm", "right": "14mm"})
        browser.close()


def safe_id(s):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(s)).strip("_") or "preventivo"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--company", required=True, help="JSON del documento settings/company")
    ap.add_argument("--quotes-dir", required=True, help="Cartella con un JSON per preventivo (doc quotes/<id>.json)")
    ap.add_argument("--counter", help="JSON del documento meta/counter (opzionale, solo per backup)")
    ap.add_argument("--repo-root", default=".", help="Root della repo (default: cartella corrente)")
    ap.add_argument("--force", action="store_true", help="Rigenera tutti i PDF anche se già in registry")
    args = ap.parse_args()

    repo_root = Path(args.repo_root)
    pdf_dir = repo_root / "preventivi" / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    registry_path = repo_root / "preventivi" / "registry.json"
    counter_path = repo_root / "preventivi" / "counter.json"

    company = json.loads(Path(args.company).read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else []
    registry_by_id = {r["id"]: r for r in registry}

    quotes_dir = Path(args.quotes_dir)
    quote_files = sorted(quotes_dir.glob("*.json")) if quotes_dir.exists() else []
    if not quote_files:
        print(f"Nessun preventivo trovato in {quotes_dir}")

    generated, skipped = 0, 0
    for qf in quote_files:
        doc_id = qf.stem
        quote = json.loads(qf.read_text(encoding="utf-8"))
        updated_at = quote.get("updatedAt") or quote.get("createdAt") or ""
        existing = registry_by_id.get(doc_id)
        if existing and existing.get("updatedAt") == updated_at and not args.force:
            skipped += 1
            continue

        html_str = build_html(quote, company)
        pdf_name = f"{safe_id(quote.get('number') or doc_id)}.pdf"
        pdf_path = pdf_dir / pdf_name
        render_pdf(html_str, pdf_path)

        totals = quote.get("totals") or calc_totals(quote.get("righe"))
        registry_by_id[doc_id] = {
            "id": doc_id,
            "number": quote.get("number"),
            "cliente": (quote.get("cliente") or {}).get("ragione"),
            "dataEmissione": quote.get("dataEmissione"),
            "dataValidita": quote.get("dataValidita"),
            "totali": totals,
            "pdf": f"preventivi/pdf/{pdf_name}",
            "updatedAt": updated_at,
            "syncedAt": datetime.now(timezone.utc).isoformat(),
        }
        generated += 1
        print(f"Generato: {pdf_path}")

    registry = sorted(registry_by_id.values(), key=lambda r: r.get("number") or "")
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.counter:
        counter_doc = json.loads(Path(args.counter).read_text(encoding="utf-8"))
        counter_backup = {
            "nextNumber": counter_doc.get("nextNumber", 1),
            "note": "Copia di backup del contatore vivo, che risiede nel database dell'artifact MRV Preventivi (doc meta/counter). Questo file viene aggiornato dalla routine di sincronizzazione e non va modificato a mano: in caso di conflitto vince il valore nell'artifact.",
            "lastSyncedAt": datetime.now(timezone.utc).isoformat(),
        }
        counter_path.write_text(json.dumps(counter_backup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nFatto: {generated} PDF generati/aggiornati, {skipped} già aggiornati. Registro: {registry_path}")


if __name__ == "__main__":
    sys.exit(main())
