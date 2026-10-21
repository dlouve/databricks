import json, random, csv, os, datetime as dt
from collections import defaultdict
random.seed(42)
OUT = "/home/claude/alpina_lab/data"
for d in ["landing/claims/2026-10-01","landing/claims/2026-10-02","landing/claims/2026-10-03",
          "landing/members","reference","api_mock"]:
    os.makedirs(f"{OUT}/{d}", exist_ok=True)

KANTONE = ["ZH","BE","LU","AG","SG","TG","BS","GE","VD","TI","GR","ZG"]
VN = ["Laura","Marco","Sandra","Luca","Nina","Reto","Anna","Jonas","Sara","Fabian","Lea","Simon","Mia","David","Elena","Patrick"]
NN = ["Muster","Beispiel","Fiktiv","Testmann","Probst","Erfunden","Demo","Sample","Platzhalter","Modell"]
FR = [300,500,1000,1500,2000,2500]
TARIFE = [("T01","Standard"),("T02","Hausarzt"),("T03","Telmed"),("T04","HMO")]

def member(i, franchise=None):
    return dict(member_id=f"M{i:05d}", vorname=random.choice(VN), nachname=random.choice(NN),
        geburtsdatum=(dt.date(1945,1,1)+dt.timedelta(days=random.randint(0,28000))).isoformat(),
        ahv_nr=f"999.{random.randint(1000,9999)}.{random.randint(1000,9999)}.{random.randint(10,99)}",
        kanton=random.choice(KANTONE), plz=str(random.randint(1000,9699)),
        franchise=franchise or random.choice(FR), tarif_id=random.choice(TARIFE)[0],
        email=f"m{i:05d}@example.org", gueltig_ab="2026-01-01")

# --- Members: day1 2000, day2 150 new + 100 updates
m1 = [member(i) for i in range(1,2001)]
upd = random.sample(m1, 100)
m2 = [member(i) for i in range(2001,2151)]
for u in upd:
    n = dict(u); n["franchise"] = random.choice([f for f in FR if f != u["franchise"]]); n["gueltig_ab"]="2026-10-01"
    m2.append(n)
random.shuffle(m2)
cols = list(m1[0].keys())
for name, rows in [("members_2026-10-01.csv", m1), ("members_2026-10-02.csv", m2)]:
    with open(f"{OUT}/landing/members/{name}","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";"); w.writeheader(); w.writerows(rows)
member_ids = {m["member_id"] for m in m1+m2}
member_kanton = {m["member_id"]: m["kanton"] for m in m1}
for m in m2: member_kanton[m["member_id"]] = m["kanton"]

# --- Providers (reference CSV, small -> broadcast)
TYPEN = ["Spital","Arztpraxis","Apotheke","Physiotherapie","Labor"]
prov = [dict(provider_id="P0001", name="Zentralspital Alpina (fiktiv)", typ="Spital", kanton="ZH")]
for i in range(2,151):
    t = random.choice(TYPEN)
    prov.append(dict(provider_id=f"P{i:04d}", name=f"{t} {random.choice(NN)} {i}", typ=t, kanton=random.choice(KANTONE)))
with open(f"{OUT}/reference/providers.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=prov[0].keys()); w.writeheader(); w.writerows(prov)

# --- Tarife via paginated mock API
tar = [dict(tarif_id=t, bezeichnung=b, rabatt_pct=r) for (t,b),r in zip(TARIFE,[0,12,15,20])]
json.dump({"data":tar[:2],"page":1,"next_page":"tarife_page2.json"}, open(f"{OUT}/api_mock/tarife_page1.json","w"), indent=2, ensure_ascii=False)
json.dump({"data":tar[2:],"page":2,"next_page":None}, open(f"{OUT}/api_mock/tarife_page2.json","w"), indent=2, ensure_ascii=False)

# --- Claims
ICD = [("J06.9","Akute Infektion obere Atemwege"),("M54.5","Kreuzschmerz"),("I10","Essentielle Hypertonie"),
       ("E11.9","Diabetes mellitus Typ 2"),("F32.1","Mittelgradige depressive Episode"),("S93.4","Verstauchung Sprunggelenk"),
       ("K21.9","Gastroösophageale Refluxkrankheit"),("Z00.0","Allgemeine Untersuchung")]
POS = ["00.0010","00.0020","00.0030","39.0020","Pharma-001","Physio-7301","Labor-1001"]
cid = 0
all_valid = []   # (record) for expected computation
def mk_claim(day, version=1, base=None):
    global cid
    if base is None:
        cid += 1
        claim_id = f"C{cid:06d}"
        mid = random.choice(sorted(member_ids if day!="2026-10-01" else {m["member_id"] for m in m1}))
        provider = "P0001" if random.random() < 0.35 else random.choice(prov[1:])["provider_id"]
        icd = random.choice(ICD)
        d = dt.date(2026,7,1)+dt.timedelta(days=random.randint(0,90))
    else:
        claim_id, mid, provider = base["claim_id"], base["member_id"], base["leistungserbringer_id"]
        icd = (base["diagnose"]["icd10"], base["diagnose"]["beschreibung"]); d=None
    positionen = [dict(tarifposition=random.choice(POS), menge=random.randint(1,3),
                       betrag=round(random.uniform(15,900),2)) for _ in range(random.randint(1,4))]
    total = round(sum(p["betrag"] for p in positionen),2)
    rec = dict(claim_id=claim_id, version=version, member_id=mid, leistungserbringer_id=provider,
               diagnose=dict(icd10=icd[0], beschreibung=icd[1]), positionen=positionen,
               betrag_total=total, behandlungsdatum=(d.isoformat() if d else base["behandlungsdatum"]),
               eingang_ts=f"{day}T{random.randint(6,22):02d}:{random.randint(0,59):02d}:00",
               kanal=random.choice(["papier","app","edi"]))
    return rec

days = {}
# Day 1
d1 = [mk_claim("2026-10-01") for _ in range(4000)]
# Day 2
d2 = [mk_claim("2026-10-02") for _ in range(3500)]
resent = random.sample(d1, 120)          # exact duplicates resent
d2 += [dict(r) for r in resent]
# Day 3 (schema evolution: telemedizin)
d3 = [mk_claim("2026-10-03") for _ in range(3500)]
for r in d3: r["telemedizin"] = random.random() < 0.2
corr = random.sample(d1+d2[:3500], 80)    # corrections version 2
for b in corr:
    c = mk_claim("2026-10-03", version=2, base=b); c["telemedizin"]=False; d3.append(c)
corr_ids = {c["claim_id"] for c in corr}

def dirty(rows, day):
    for r in rows:
        if r["claim_id"] in corr_ids and r["version"]==2: continue
        x = random.random()
        if x < 0.03:   r["betrag_total"] = str(r["betrag_total"]).replace(".", ",")   # string w/ comma -> still valid
        elif x < 0.045: r["betrag_total"] = None                                        # invalid
        elif x < 0.07:
            d = dt.date.fromisoformat(r["behandlungsdatum"]); r["behandlungsdatum"] = d.strftime("%d.%m.%Y")  # valid alt format
        elif x < 0.08: r["behandlungsdatum"] = "unbekannt"                              # invalid
        elif x < 0.09: r["member_id"] = f"M9{random.randint(1000,9999)}"                # orphan
        elif x < 0.10:  # positionen sum mismatch (DQ warning, not quarantine)
            r["betrag_total"] = round(float(r["betrag_total"]) + 50.0, 2) if r["betrag_total"] is not None else None
dirty(d1, "d1"); dirty([r for r in d2 if r not in resent], "d2"); dirty(d3, "d3")
# resent rows: copy dirty state of originals
d2 = d2[:3500] + [dict(r) for r in resent]
random.shuffle(d2); random.shuffle(d3)

def write(rows, day, nfiles, malformed=0):
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    bad = []
    for _ in range(malformed):
        i = random.randrange(len(lines)); bad.append(i)
        lines[i] = lines[i][: len(lines[i])//2]   # truncated JSON
    chunk = len(lines)//nfiles + 1
    for k in range(nfiles):
        with open(f"{OUT}/landing/claims/{day}/claims_{day.replace('-','')}_{k+1:03d}.json","w",encoding="utf-8") as f:
            f.write("\n".join(lines[k*chunk:(k+1)*chunk])+"\n")
    return {i for i in bad}
write(d1,"2026-10-01",2)
bad2 = write(d2,"2026-10-02",2,malformed=6)
write(d3,"2026-10-03",3)

# ---------- Expected results ----------
raw = [r for r in d1] + [r for i,r in enumerate(d2) if i not in bad2] + d3
def parse_amt(v):
    if v is None: return None
    try: return float(str(v).replace(",", "."))
    except: return None
def parse_date(s):
    for f in ("%Y-%m-%d","%d.%m.%Y"):
        try: return dt.datetime.strptime(s,f).date()
        except: pass
    return None
latest = {}
for r in raw:
    k = r["claim_id"]
    if k not in latest or (r["version"], r["eingang_ts"]) > (latest[k]["version"], latest[k]["eingang_ts"]):
        latest[k] = r
silver, quarantine, mismatch = [], [], 0
for r in latest.values():
    a, d = parse_amt(r["betrag_total"]), parse_date(r["behandlungsdatum"])
    if a is None or d is None or r["member_id"] not in member_ids: quarantine.append(r); continue
    silver.append((r, a, d))
    if abs(sum(p["betrag"] for p in r["positionen"]) - a) > 0.01: mismatch += 1
by_kt = defaultdict(float)
for r,a,d in silver: by_kt[member_kanton[r["member_id"]]] += a
p1 = sum(1 for r,a,d in silver if r["leistungserbringer_id"]=="P0001")
lines_total = len(d1)+len(d2)+len(d3)
with open("/home/claude/alpina_lab/expected_results.md","w",encoding="utf-8") as f:
    f.write("# Erwartete Ergebnisse (Kontrollwerte)\n\nAus dem Generator berechnet (Python, unabhaengig von Spark). Abweichungen um wenige Zeilen koennen auf eine abweichende Regelauslegung hindeuten - dann die Regel im README nochmals lesen.\n\n")
    f.write("| Kontrolle | Wert |\n|---|---|\n")
    f.write(f"| JSON-Zeilen total in landing/claims (alle 3 Tage) | {lines_total} |\n")
    f.write(f"| davon defekte (abgeschnittene) JSON-Zeilen, nur Tag 2 | {len(bad2)} |\n")
    f.write(f"| Members Bronze nach COPY INTO Tag 1 | {len(m1)} |\n")
    f.write(f"| Members Bronze nach COPY INTO Tag 2 (Append) | {len(m1)+len(m2)} |\n")
    f.write(f"| COPY INTO erneut ausgefuehrt: neu geladene Zeilen | 0 |\n")
    f.write(f"| Members Silver nach MERGE (eindeutige member_id) | {len(member_ids)} |\n")
    f.write(f"| Eindeutige claim_id nach Dedup (vor Validierung) | {len(latest)} |\n")
    f.write(f"| Silver claims (valide) | {len(silver)} |\n")
    f.write(f"| Quarantaene claims | {len(quarantine)} |\n")
    f.write(f"| Silver claims mit Summen-Abweichung positionen vs. betrag_total (> 0.01) | {mismatch} |\n")
    f.write(f"| Silver claims beim Leistungserbringer P0001 (Skew) | {p1} ({p1/len(silver):.1%}) |\n")
    f.write(f"| Silver-Zeilen nach explode(positionen) | {sum(len(r['positionen']) for r,a,d in silver)} |\n\n")
    f.write("## Gold: Summe betrag_total (CHF) je Kanton des Versicherten\n\n| Kanton | Summe CHF |\n|---|---|\n")
    for k in sorted(by_kt): f.write(f"| {k} | {by_kt[k]:,.2f} |\n")
print(lines_total, len(bad2), len(latest), len(silver), len(quarantine), mismatch)
