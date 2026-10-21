# Erwartete Ergebnisse (Kontrollwerte)

Aus dem Generator berechnet (Python, unabhaengig von Spark). Abweichungen um wenige Zeilen koennen auf eine abweichende Regelauslegung hindeuten - dann die Regel im README nochmals lesen.

| Kontrolle | Wert |
|---|---|
| JSON-Zeilen total in landing/claims (alle 3 Tage) | 11200 |
| davon defekte (abgeschnittene) JSON-Zeilen, nur Tag 2 | 6 |
| Members Bronze nach COPY INTO Tag 1 | 2000 |
| Members Bronze nach COPY INTO Tag 2 (Append) | 2250 |
| COPY INTO erneut ausgefuehrt: neu geladene Zeilen | 0 |
| Members Silver nach MERGE (eindeutige member_id) | 2150 |
| Eindeutige claim_id nach Dedup (vor Validierung) | 10996 |
| Silver claims (valide) | 10585 |
| Quarantaene claims | 411 |
| Silver claims mit Summen-Abweichung positionen vs. betrag_total (> 0.01) | 109 |
| Silver claims beim Leistungserbringer P0001 (Skew) | 3734 (35.3%) |
| Silver-Zeilen nach explode(positionen) | 26507 |

## Gold: Summe betrag_total (CHF) je Kanton des Versicherten

| Kanton | Summe CHF |
|---|---|
| AG | 1,066,014.87 |
| BE | 992,835.80 |
| BS | 975,650.71 |
| GE | 979,426.99 |
| GR | 1,038,227.17 |
| LU | 1,064,058.65 |
| SG | 1,086,881.52 |
| TG | 912,974.40 |
| TI | 975,966.12 |
| VD | 988,572.48 |
| ZG | 1,108,134.30 |
| ZH | 911,468.63 |
