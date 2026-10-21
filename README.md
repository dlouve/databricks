# Alpina Claims Lab – Hands-on für Databricks Data Engineer Associate

Ausrichtung am Exam Guide, Stand **4. Mai 2026**. Alle Daten sind synthetisch; Namen, AHV-Nummern (Präfix `999`, bewusst ungültig) und Leistungserbringer sind erfunden.

## Szenario

Die fiktive **Alpina Krankenversicherung** löst ihre alte Leistungsabrechnungs-Strecke ab. Täglich kommen:

| Quelle | Format | Pfad | Besonderheit |
|---|---|---|---|
| Leistungsabrechnungen (Claims) | JSON Lines, verschachtelt | `landing/claims/<datum>/` | Tag 2: Duplikate + 6 defekte Zeilen. Tag 3: neue Spalte `telemedizin` + 80 Korrekturen (`version = 2`) |
| Versichertenbestand | CSV, Trenner `;` | `landing/members/` | Tag 2: 150 Neuzugänge + 100 Franchise-Änderungen |
| Leistungserbringer | CSV | `reference/providers.csv` | 150 Zeilen → Broadcast-Kandidat. `P0001` hat ~35 % aller Claims → Skew |
| Tarife | paginierte "REST"-Antworten | `api_mock/tarife_page*.json` | `next_page`-Verweis wie bei einer echten API |

Sensible Felder: `ahv_nr`, `geburtsdatum`, `email` (Members) und `diagnose` (Claims).

**Kontrollwerte** für jede Stufe stehen in `expected_results.md`.

## Regeln (fachlich, verbindlich für die Kontrollwerte)

1. **Dedup Claims:** pro `claim_id` gewinnt die höchste `version`, bei Gleichstand der späteste `eingang_ts`. *Erst* deduplizieren, *dann* validieren.
2. **Betrag:** `betrag_total` kann Zahl, String mit Komma (`"123,45"`) oder `null` sein. Komma → Punkt, cast auf `DECIMAL(12,2)`.
3. **Datum:** `behandlungsdatum` in `yyyy-MM-dd` oder `dd.MM.yyyy`. Alles andere ist ungültig.
4. **Quarantäne:** Betrag ungültig/null, Datum ungültig, oder `member_id` nicht im Versichertenbestand (Tag 1 + Tag 2).
5. **DQ-Warnung (keine Quarantäne):** Summe `positionen.betrag` weicht um > 0.01 von `betrag_total` ab.
6. **Members Silver:** SCD Typ 1 per `MERGE` auf `member_id` (neuester `gueltig_ab` gewinnt).

## Setup

1. Catalog `alpina_dev` mit Schemas `landing`, `bronze`, `silver`, `gold` anlegen.
2. Managed Volume `alpina_dev.landing.files` anlegen und den Ordner `data/` dort hochladen. **Für Tag-für-Tag-Simulation zuerst nur `claims/2026-10-01` hochladen.**
3. Repo (dieser Ordner) in GitHub/GitLab pushen und als **Git Folder** einbinden.

**Umgebung – bitte selbst prüfen:** Die Free Edition bietet laut Databricks-Doku nur Serverless Compute. Nach meinem Kenntnisstand heisst das: keine eigenen Cluster, eingeschränkte Spark UI und nur wenige `spark.conf`-Parameter. Für die Übungen 3.5 und 6.3 brauchst du darum wahrscheinlich einen Trial-Workspace. Auch ob ABAC, Lakeflow Connect Managed Connectors und File-Arrival-Trigger in deinem Workspace verfügbar sind, habe ich nicht verifiziert.

---

## Abschnitt 1 – Platform (6 %)

- **1.1** Erkläre (schriftlich, 5 Sätze): Wo liegen die Daten einer *managed* Delta-Tabelle physisch, und was passiert bei `DROP TABLE`?
- **1.2** Wähle Compute für drei Workloads und begründe: (a) nächtlicher Batch-Job, (b) Analysten mit Ad-hoc-SQL, (c) interaktive Entwicklung. Stichworte: Jobs Compute, SQL Warehouse (serverless/pro), All-Purpose, Serverless – Kostenmodell und Startzeit.
- **1.3** Nach dem ersten Silver-Load: `DESCRIBE HISTORY`, dann absichtlich `DELETE FROM silver.claims WHERE kanal = 'app'` und per `RESTORE TABLE ... TO VERSION AS OF` zurückholen.

## Abschnitt 2 – Ingestion (21 %)

- **2.1 COPY INTO:** `members_*.csv` nach `bronze.members` (Optionen: `header`, `sep`, `mergeSchema`). Danach denselben Befehl **nochmal** ausführen → Kontrollwert: 0 neue Zeilen. Erkläre, warum.
- **2.2 Auto Loader:** `landing/claims/` nach `bronze.claims` mit `cloudFiles.format = json`, `cloudFiles.schemaLocation`, Trigger `availableNow`. Nur Tag 1 vorhanden.
  - Frage vorab: Mit welchem Typ inferiert Auto Loader JSON-Spalten standardmässig? Teste mit und ohne `cloudFiles.inferColumnTypes`.
  - Setze `cloudFiles.schemaHints` für `betrag_total DOUBLE` und beobachte, was mit `"123,45"` passiert (`_rescued_data`?).
- **2.3 Schema-Evolution:** Tag 2 und Tag 3 hochladen, Stream erneut starten. Bei Tag 3 (`telemedizin`) sollte der Stream im Modus `addNewColumns` *einmal* fehlschlagen und beim Neustart durchlaufen – verifiziere das. Vergleiche mit `rescue`, `failOnNewColumns`, `none`.
- **2.4 Defekte Zeilen:** Finde die 6 abgeschnittenen JSON-Zeilen aus Tag 2. Wo landen sie (Nullzeile, `_rescued_data`, `_corrupt_record`)? Ich bin mir hier nicht sicher, wie sich Auto Loader genau verhält – genau das ist die Übung.
- **2.5 REST-Client:** Notebook, das `tarife_page1.json` liest, `next_page` folgt und das Ergebnis nach `bronze.tarife` schreibt. (Mit echter API: `requests.get` im Loop, gleiche Logik.)
- **2.6 Entscheidungsmatrix:** Für jede der vier Quellen: Auto Loader vs. COPY INTO vs. Lakeflow Connect (standard/managed) vs. JDBC – mit Begründung zu Volumen, Frequenz, Format, Governance.

## Abschnitt 3 – Transformation & Modellierung (22 %)

- **3.1 Silver Claims (PySpark):** Regeln 1–4 umsetzen → `silver.claims` + `silver.claims_quarantine`. Hinweis: `row_number()` über Window, `try_to_date`/`coalesce` für zwei Formate.
- **3.2 Explode:** `positionen` → `silver.claim_positionen` (eine Zeile pro Position). Diagnose-Struct in Spalten flachklopfen.
- **3.3 Joins:** Claims ⨝ Members (inner), Claims ⟕ Providers (left, mit `broadcast()`), Tarife. Zeige im Plan (`explain()`), dass ein BroadcastHashJoin verwendet wird.
- **3.4 Aggregationen:** `count`, `approx_count_distinct(member_id)` vs. `countDistinct` vergleichen, `mean`, `summary()`.
- **3.5 Tuning:** Vor/nach Messung mit `spark.sql.shuffle.partitions` (200 vs. 8) und `spark.sql.autoBroadcastJoinThreshold = -1`. Dauer notieren.
- **3.6 Gold:** Baue *dieselbe* Kennzahl (Summe CHF je Kanton und Monat) als **View**, **Materialized View** und **Tabelle**. Dazu eine **Streaming Table** auf `bronze.claims`. Notiere je: wann aktualisiert, was kostet es, wer würde es nutzen.
- **3.7 DQ:** Regel 5 als Check. Bonus: dieselbe Logik als Lakeflow Declarative Pipeline mit `EXPECT ... ON VIOLATION DROP ROW` bzw. `WARN`.

## Abschnitt 4 – Lakeflow Jobs (16 %)

Job `alpina_daily`, zuerst per UI:

```
ingest_members ──► silver_members ─┐
                                   ├─► dq_check ─► if quarantine > 0 ─► notify_quarantine
ingest_claims  ──► silver_claims ──┘                 └─► gold_refresh ─► for_each(kanton) ─► kanton_report
```

- **4.1** Tasks: Notebook, SQL-Query, Pipeline-Task (aus 3.7), Dashboard-Task (optional).
- **4.2** `ingest_claims` mit 2 Retries (Grund: Auto-Loader-Fehler bei neuer Spalte, siehe 2.3).
- **4.3** If/else-Task über einen Task-Value aus `dq_check` (`dbutils.jobs.taskValues.set`).
- **4.4** For-each-Task über die 12 Kantone.
- **4.5** Trigger vergleichen: zeitbasiert vs. **File Arrival** auf `landing/claims/` vs. **Table Update** auf `silver.claims`. Teste File Arrival, indem du Tag 3 erst nach dem Aktivieren hochlädst.

## Abschnitt 5 – CI/CD (10 %)

- **5.1** Im Git Folder: Branch `feature/dq-checks` anlegen, Notebook ändern, commit, push, Pull Request erstellen.
- **5.2** `databricks.yml` vervollständigen (TODOs): Job aus Abschnitt 4 als Resource, `${var.catalog}` in die Tasks durchreichen.
- **5.3** CLI: `databricks bundle validate`, `databricks bundle deploy -t dev`, `databricks bundle run alpina_daily -t dev`. Prüfe, wie `mode: development` den Jobnamen ändert.
- **5.4** Ziel `prod` deployen (oder nur validieren) – woran erkennst du, dass `alpina_prod` verwendet wird?

## Abschnitt 6 – Troubleshooting & Optimierung (10 %)

- **6.1** Job 5x laufen lassen, Run History ansehen: Dauer im Vergleich zur Baseline.
- **6.2** Absichtlich Fehler einbauen (falscher Pfad in `silver_members`): im DAG den Upstream-Blocker erkennen, "Repair run" nutzen.
- **6.3 Skew:** `notebooks/99_generate_skew_data.py` ausführen und das dort beschriebene Experiment machen (AQE an/aus, Broadcast, Salting). In der Spark UI: Max- vs. Median-Shuffle-Read, Spill.
- **6.4** `silver.claims` mit `CLUSTER BY (leistungserbringer_id, behandlungsdatum)` neu anlegen, `OPTIMIZE`. Prüfe, ob Predictive Optimization im Catalog aktiv ist.
- **6.5** Fehlerbilder durchdenken: Bibliothekskonflikt (zwei Versionen von `requests`), OOM auf dem Driver durch `collect()` auf 20 Mio. Zeilen.

## Abschnitt 7 – Governance (15 %)

- **7.1** `silver.members` als managed Tabelle, `bronze.providers_ext` als external (falls du eine External Location hast). Unterschied bei `DROP` testen; Konvertierung managed ↔ external recherchieren und versuchen.
- **7.2** Gruppen `alpina_analysts`, `alpina_engineers`, `team_ostschweiz` anlegen. `GRANT USE CATALOG / USE SCHEMA / SELECT`, ein `REVOKE`. Prüfe, ob `DENY` in deinem Workspace funktioniert – nach meinem Wissen ist das in Unity Catalog nicht überall verfügbar, der Exam Guide nennt es aber.
- **7.3 Column Mask:** `ahv_nr` nur für `alpina_engineers` im Klartext, sonst `999.****.****.**`. `diagnose_icd10` für Analysten auf das Kapitel kürzen (`J06.9` → `J`).
- **7.4 Row Filter:** `team_ostschweiz` sieht nur Claims von Versicherten aus SG und TG.
- **7.5 ABAC:** Tag `pii = true` auf die sensiblen Spalten, dann *eine* Policy statt einzelner Masks. Verfügbarkeit/Status (Preview vs. GA) bitte in der aktuellen Doku prüfen.

---

## Selbstcheck nach dem Lab
Kannst du ohne Nachschlagen beantworten, wann du COPY INTO statt Auto Loader nimmst, was eine Streaming Table von einer Materialized View unterscheidet, und warum ein grösserer Cluster bei Skew kaum hilft? Dann passen die Abschnitte 2, 3 und 6.
