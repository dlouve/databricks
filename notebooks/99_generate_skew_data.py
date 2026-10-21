# Databricks notebook source
# MAGIC %md
# MAGIC ## Skew-Daten fuer Abschnitt 6 (Spark UI, Skew, Shuffle, Spill)
# MAGIC Die Lab-Dateien sind zu klein, um Skew in der Spark UI sichtbar zu machen.
# MAGIC Dieses Notebook erzeugt ~20 Mio. synthetische Claims, davon ~60 % bei einem einzigen Leistungserbringer.
# MAGIC **Hinweis:** Auf Serverless (z.B. Free Edition) sind Spark UI und viele `spark.conf`-Einstellungen eingeschraenkt.
# MAGIC Fuer diese Uebung brauchst du nach meinem Kenntnisstand klassisches Compute (z.B. Trial-Workspace). Bitte selbst pruefen.

# COMMAND ----------

dbutils.widgets.text("catalog", "alpina_dev")
dbutils.widgets.text("rows", "20000000")
catalog = dbutils.widgets.get("catalog")
n = int(dbutils.widgets.get("rows"))

from pyspark.sql import functions as F

df = (spark.range(n)
      .withColumn("claim_id", F.format_string("S%09d", "id"))
      .withColumn("leistungserbringer_id",
                  F.when(F.rand(1) < 0.6, F.lit("P0001"))
                   .otherwise(F.format_string("P%04d", (F.rand(2) * 149 + 2).cast("int"))))
      .withColumn("betrag_total", F.round(F.rand(3) * 2000, 2))
      .drop("id"))

df.write.mode("overwrite").saveAsTable(f"{catalog}.bronze.claims_skew")

# COMMAND ----------

# MAGIC %md
# MAGIC Experiment (siehe README, Abschnitt 6):
# MAGIC 1. AQE aus: `spark.conf.set("spark.sql.adaptive.enabled", "false")`, `spark.sql.autoBroadcastJoinThreshold = -1`
# MAGIC 2. Join `claims_skew` mit einer 150-Zeilen-Providertabelle, die du kuenstlich auf viele Zeilen je provider_id aufblaest
# MAGIC 3. Stage in der Spark UI ansehen: Min/Median/Max Shuffle Read, Task-Dauer, Spill
# MAGIC 4. Dasselbe mit AQE + Skew-Join-Handling, danach mit Broadcast, danach mit Salting. Laufzeiten notieren.
