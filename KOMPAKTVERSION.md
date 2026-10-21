# Alpina Claims Lab – Kompaktversion (ca. 3,5–4 Stunden)

Alle sieben Exam-Abschnitte sind drin. Gekürzt wird über **Kombinieren statt Weglassen**:
- Eine Lakeflow-Pipeline deckt Streaming Table, Materialized View, Expectations, Explode, Broadcast-Join und Liquid Clustering in einem Schritt ab.
- Du arbeitest von Anfang an auf einem Git-Branch, so ist CI/CD nebenbei erledigt.
- Tag 3 testet Schema-Evolution, File-Arrival-Trigger und Retries zusammen.

Zeitangaben sind grobe Schätzungen. Daten, Regeln (README) und `expected_results.md` bleiben gleich.
Syntaxbeispiele habe ich aus meinem Wissen geschrieben, nicht in einem Workspace getestet.

---

## Block 1 – Setup + Branch (15 Min.) · Abschnitte 1, 5

1. Repo pushen, als **Git Folder** einbinden, sofort Branch `feature/lab` anlegen. Ab jetzt alles dort.
2. Catalog, Schemas, Volume anlegen:
   ```sql
   CREATE CATALOG IF NOT EXISTS alpina_dev;   -- falls nicht erlaubt: Default-Catalog nutzen
   CREATE SCHEMA IF NOT EXISTS alpina_dev.bronze;
   CREATE SCHEMA IF NOT EXISTS alpina_dev.silver;
   CREATE SCHEMA IF NOT EXISTS alpina_dev.gold;
   CREATE SCHEMA IF NOT EXISTS alpina_dev.landing;
   CREATE VOLUME IF NOT EXISTS alpina_dev.landing.files;
   ```
3. Hochladen: `reference/`, `landing/members/` (beide Dateien), `landing/claims/2026-10-01/` und `2026-10-02/`. **Tag 3 noch nicht.**
4. Nebenbei (Abschnitt 1, ohne Bau): Notiere, welches Compute du wofür nimmst – Notebook, Pipeline, Job, SQL Warehouse – und warum.

## Block 2 – Members per COPY INTO + MERGE (20 Min.) · Abschnitte 2, 3

Notebook `01_members`:
1. `COPY INTO alpina_dev.bronze.members` aus `landing/members/` (`FORMAT_OPTIONS('header'='true','sep'=';')`, `COPY_OPTIONS('mergeSchema'='true')`). Zweimal ausführen. Kontrolle: 2'250 Zeilen, der zweite Lauf lädt 0.
2. `MERGE INTO silver.members` auf `member_id`, neuester `gueltig_ab` gewinnt. Kontrolle: 2'150.

## Block 3 – Lakeflow-Pipeline für Claims (75 Min.) · Abschnitte 2, 3, 6

Pipeline (SQL oder Python), Ziel-Catalog `alpina_dev`, Ziel-Schema z.B. `silver`. Tabellen:

| Tabelle | Typ | Inhalt |
|---|---|---|
| `bronze_claims` | Streaming Table | Auto Loader auf `landing/claims/` (z.B. `STREAM read_files(..., format => 'json')`) |
| `providers` | Materialized View | CSV aus `reference/` |
| `silver_claims` | Materialized View | Regeln 1–4: Dedup, Betrag, Datum, Join auf `silver.members`. Expectations mit `ON VIOLATION DROP ROW`; Regel 5 als Expectation ohne Aktion (nur Warnung) |
| `claims_quarantine` | Materialized View | die verworfenen Fälle (umgekehrte Bedingung) |
| `claim_positionen` | Materialized View | `explode(positionen)` |
| `gold_kanton_monat` | Materialized View | Summe CHF und `approx_count_distinct(member_id)` je Kanton und Monat, Join auf `providers` mit Broadcast-Hint, `CLUSTER BY (kanton)` |

Danach:
1. Pipeline starten, im **Event Log / UI** die Expectation-Metriken ansehen (wie viele Zeilen verworfen?).
2. Zusätzlich eine normale **View** auf `gold_kanton_monat` anlegen. Notiere in je einem Satz: View vs. Materialized View vs. Streaming Table vs. Tabelle.
3. Prüfe das von Auto Loader inferierte Schema: Welchen Typ hat `betrag_total` bei gemischten Werten?

## Block 4 – Job, Tag 3, Monitoring (40 Min.) · Abschnitte 4, 2, 6

1. Job `alpina_daily`:
   `01_members` (Notebook) → `claims_pipeline` (Pipeline-Task) → `dq_check` (Notebook, setzt Task-Value `quarantine_count`) → **If/else**: bei > 0 ein Notiz-Task.
   Pipeline-Task mit **2 Retries**.
2. **File-Arrival-Trigger** auf `landing/claims/` aktivieren, dann `claims/2026-10-03/` hochladen.
3. Beobachten: Startet der Job selbst? Wie reagiert die Pipeline auf die neue Spalte `telemedizin`? Ich erwarte einen Neustart des Flows oder einen Retry, habe das aber nicht getestet.
4. Ergebnisse mit `expected_results.md` vergleichen (Silver 10'585, Quarantäne 411, Positionen 26'507).
5. **Monitoring:** Pfad in `dq_check` absichtlich falsch setzen, Job laufen lassen, im DAG den Fehler finden, korrigieren, **Repair Run**. Run History: Laufzeiten vergleichen.

## Block 5 – Governance (30 Min.) · Abschnitt 7

1. Gruppen `alpina_analysts`, `alpina_engineers`, `team_ostschweiz`. `GRANT USE CATALOG / USE SCHEMA / SELECT` an Analysts, ein `REVOKE`, `DENY` versuchen (Verfügbarkeit prüfen).
2. **Column Mask** auf `silver.members.ahv_nr` (Klartext nur für Engineers).
3. **Row Filter** auf `silver_claims`: `team_ostschweiz` sieht nur SG/TG. Falls Masks/Filter auf Pipeline-Tabellen bei dir nicht gehen: auf einer Kopie als normale Tabelle testen.
4. **ABAC:** Tag `pii` auf `geburtsdatum` und `email`, eine Policy mit Maskierung. Verfügbarkeit (Preview/GA) bitte in der Doku prüfen.
5. Managed vs. external: Bei einer Tabelle `DESCRIBE EXTENDED` ansehen und notieren, was bei `DROP` mit den Daten passiert.

Test: dich selbst einer Gruppe hinzufügen/entfernen.

## Block 6 – CI/CD abschliessen (30 Min.) · Abschnitt 5

1. Im Git Folder: Commit + Push von `feature/lab`, Pull Request erstellen.
2. Job-Definition als YAML aus der Job-UI kopieren (meines Wissens gibt es diese Ansicht) und in `databricks.yml` unter `resources.jobs` einsetzen. Catalog durch `${var.catalog}` ersetzen.
3. Lokal mit der Databricks CLI: `databricks bundle validate`, dann `databricks bundle deploy -t dev`. Schau dir an, wie `mode: development` den Jobnamen verändert.
4. Für `prod` nur `validate -t prod` ausführen und prüfen, dass `alpina_prod` aufgelöst wird.

## Block 7 – Optimierung als Theorie (15 Min.) · Abschnitt 6

In der Free Edition fehlt die volle Spark UI. Deshalb hier nur denken, nicht bauen:
- Beispielfrage 1 im Exam Guide lösen. Warum hilft AQE-Skew-Handling, ein grösserer Cluster aber kaum?
- Was bewirken `spark.sql.shuffle.partitions` und `autoBroadcastJoinThreshold`? Bezug auf dein `gold_kanton_monat` (P0001 hat 35 % der Claims).
- Woran erkennst du Spill, Skew und Shuffle in den Stage-Metriken?
- Liquid Clustering: `DESCRIBE DETAIL` auf `gold_kanton_monat` – sind die Clustering-Spalten gesetzt? Was macht Predictive Optimization zusätzlich?

Optional mit Trial-Workspace: `notebooks/99_generate_skew_data.py`.

---

**Weggelassen** (geringe Prüfungsgewichtung oder bereits durch andere Blöcke abgedeckt): REST-Mock, For-each-Task, separater Vergleich View/Tabelle über 3 Varianten, Shuffle-Tuning-Messung.
