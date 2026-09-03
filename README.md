# MRV — Nightly Prospecting Database

Repository di supporto per la routine cloud notturna di CRM prospecting di MRV Consulting.

## Struttura

- `data/db_prospect_master.csv` — database cumulativo di tutti i prospect trovati (seed iniziale importato da `DB_Prospect_CRM_Veneto` e `prospect_lombardia_crm.xlsx` su Google Drive, 164 aziende). Colonne:
  `SETTORE, SOTTOCATEGORIA, AZIENDA, PROVINCIA, SITO, TELEFONO, MAIL_GENERICA, NOME_DECISORE, RUOLO, LINKEDIN_DECISORE, SEGNALI_CRM, PRIORITA, FONTE_VERIFICA, DATA_INSERIMENTO`
  **Questo file è la sorgente dati "grezza"**, usata dalla routine per il dedup: non è il file da usare per le azioni commerciali.
- `data/db_prospect_master.xlsx` — **il deliverable pronto per le azioni commerciali** (import CRM, filtri, mail merge): stesso contenuto del CSV, generato/aggiornato da `scripts/export_xlsx.py`, con lo stesso stile grafico dei DB prospect già in uso (`DB_Prospect_CRM_Veneto.xlsx`, `prospect_lombardia_crm.xlsx`) — intestazione colorata, colonna `REGIONE` derivata dalla provincia, autofiltro, riga congelata, colori per `PRIORITA` (ALTA verde / MEDIA giallo / BASSA rosso), e un foglio `Riepilogo` con i conteggi per provincia e priorità.
- `data/rotation_state.json` — stato della rotazione notturna: lista province (ciclo tutta Italia), lista settori (5 macro-settori a priorità ALTA), indice della prossima provincia da lavorare, contatore cicli.
- `data/runs/` — un file per notte con il log/riepilogo tecnico di quella run (creato dalla routine). **È un log interno, non il deliverable**: il file da usare per le azioni commerciali è sempre `data/db_prospect_master.xlsx`.
- `scripts/export_xlsx.py` — rigenera `data/db_prospect_master.xlsx` a partire da `data/db_prospect_master.csv`. Uso manuale: `pip install openpyxl && python3 scripts/export_xlsx.py`.

## Come funziona la routine

Ogni notte un agente cloud:
1. Legge `data/rotation_state.json`, prende la provincia a `next_index`.
2. Per quella provincia, ricerca prospect in 5 macro-settori in parallelo (uno per settore): Distribuzione, Servizi B2B, Software/Tech B2B, Logistica, Agenzie/Rappresentanza.
3. Deduplica i risultati contro `data/db_prospect_master.csv` (per nome azienda + sito).
4. Aggiunge le nuove righe a `data/db_prospect_master.csv`.
5. Rigenera `data/db_prospect_master.xlsx` eseguendo `scripts/export_xlsx.py` (il deliverable commerciale).
6. Scrive un riepilogo tecnico in `data/runs/YYYY-MM-DD.md`.
7. Aggiorna `next_index` (incrementa, torna a 0 a fine lista) e `cycle_count`/`last_run_utc`/`last_province` in `rotation_state.json`.
8. Commit + push di tutte le modifiche.

Target volume: ~15-20 aziende per settore a notte (~75-100 totali/notte).

## Profilo target (da skill crm-prospecting MRV)

PMI italiane (5–250 dipendenti) con rete commerciale propria (agenti, commerciali), base clienti ricorrente, più reparti, segnali di crescita.

**Esclusioni**: <2 dipendenti senza forza vendita, micro-artigianato, enti pubblici/ONLUS, aziende già presenti in `db_prospect_master.csv`.
