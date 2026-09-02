# Prova manuale — Provincia di Torino (2026-09-02)

Esecuzione di test manuale (non parte del ciclo di rotazione automatico — `rotation_state.json` non è stato toccato) per validare la pipeline prima dell'avvio della routine notturna.

## Metodo
5 agenti indipendenti in parallelo, uno per settore, target 5 aziende verificate ciascuno (scala ridotta rispetto al target notturno di 15-20/settore).

## Risultati per settore

| Settore | Aziende trovate | Priorità ALTA | Note |
|---|---|---|---|
| Distribuzione | 5 | 3 | tutte verificate su sito ufficiale |
| Servizi B2B | 5 | 2 | — |
| Software/Tech B2B | 5 | 4 | Orbyta Tech segnalata al limite superiore range PMI (250 dip.) |
| Logistica | 5 | 2 | 3 candidati scartati in fase di ricerca: Italmondo e Gazzotti (sede legale fuori provincia), Elpe Global (fuori range PMI, 1000+ dipendenti) |
| Agenzie/Rappresentanza | 5 | 2 | — |

**Totale: 25 aziende, 0 duplicati contro il master esistente (164 aziende Veneto+Lombardia), 25 aggiunte.**

## Esito
Pipeline validata: ricerca parallela per settore, verifica delle fonti, esclusione dei fuori-target, dedup contro il master, merge e commit funzionano come previsto. Pronta per il primo giro reale della routine notturna (parte da Aosta).
