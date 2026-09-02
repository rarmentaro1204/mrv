# MRV — Nightly Prospecting Database

Repository di supporto per la routine cloud notturna di CRM prospecting di MRV Consulting.

## Struttura

- `data/db_prospect_master.csv` — database cumulativo di tutti i prospect trovati (seed iniziale importato da `DB_Prospect_CRM_Veneto` e `prospect_lombardia_crm.xlsx` su Google Drive, 164 aziende). Colonne:
  `SETTORE, SOTTOCATEGORIA, AZIENDA, PROVINCIA, SITO, TELEFONO, MAIL_GENERICA, NOME_DECISORE, RUOLO, LINKEDIN_DECISORE, SEGNALI_CRM, PRIORITA, FONTE_VERIFICA, DATA_INSERIMENTO`
- `data/rotation_state.json` — stato della rotazione notturna: lista province (ciclo tutta Italia), lista settori (5 macro-settori a priorità ALTA), indice della prossima provincia da lavorare, contatore cicli.
- `data/runs/` — un file per notte con il log/riepilogo di quella run (creato dalla routine).

## Come funziona la routine

Ogni notte un agente cloud:
1. Legge `data/rotation_state.json`, prende la provincia a `next_index`.
2. Per quella provincia, ricerca prospect in 5 macro-settori in parallelo (uno per settore): Distribuzione, Servizi B2B, Software/Tech B2B, Logistica, Agenzie/Rappresentanza.
3. Deduplica i risultati contro `data/db_prospect_master.csv` (per nome azienda + sito).
4. Aggiunge le nuove righe a `data/db_prospect_master.csv`.
5. Scrive un riepilogo in `data/runs/YYYY-MM-DD.md`.
6. Aggiorna `next_index` (incrementa, torna a 0 a fine lista) e `cycle_count`/`last_run_utc`/`last_province` in `rotation_state.json`.
7. Commit + push di tutte le modifiche.

Target volume: ~15-20 aziende per settore a notte (~75-100 totali/notte).

## Profilo target (da skill crm-prospecting MRV)

PMI italiane (5–250 dipendenti) con rete commerciale propria (agenti, commerciali), base clienti ricorrente, più reparti, segnali di crescita.

**Esclusioni**: <2 dipendenti senza forza vendita, micro-artigianato, enti pubblici/ONLUS, aziende già presenti in `db_prospect_master.csv`.
