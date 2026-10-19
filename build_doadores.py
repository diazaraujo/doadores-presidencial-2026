# -*- coding: utf-8 -*-
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RECIBOS = DATA / "receitas_candidatos_2026_BR.csv"
ORIGINARIO = DATA / "receitas_candidatos_doador_originario_2026_BR.csv"
if not RECIBOS.exists() or not ORIGINARIO.exists():
    raise SystemExit(
        "Faltan los CSV en data/. Bajá el zip del TSE "
        "(prestacao_de_contas_eleitorais_candidatos_2026.zip, 17/10/2026 04:05) "
        "y dejá ahí receitas_candidatos_2026_BR.csv y "
        "receitas_candidatos_doador_originario_2026_BR.csv. "
        "Esos archivos traen CPF: no los subas a un repo público."
    )

def money(s):
    s = (s or "").strip().replace(".", "").replace(",", ".")
    if not s or s.startswith("#") or s == "-1":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0

def kept_rows(rows):
    seen = set()
    kept = []
    for r in rows:
        key = (r["VR_RECEITA"], r["DT_RECEITA"], r["DS_ORIGEM_RECEITA"], r["DS_RECEITA"], r["NR_RECIBO_DOACAO"], r["NM_DOADOR"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)
    vals = [money(r["VR_RECEITA"]) for r in kept]
    drop = None
    if len(vals) > 1:
        for i, v in enumerate(vals):
            others = sum(vals) - v
            if abs(v - others) < 0.05 and others > 0:
                drop = i
                break
    if drop is None:
        return kept
    return [r for i, r in enumerate(kept) if i != drop]

by_sq = defaultdict(list)
with open(RECIBOS, encoding="latin-1", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if row["DS_CARGO"].strip().lower() != "presidente":
            continue
        by_sq[row["SQ_CANDIDATO"]].append(row)

def donors_of(sqs):
    groups = defaultdict(list)
    for sq in sqs:
        for r in by_sq[sq]:
            groups[r["SQ_RECEITA"]].append(r)
    acc = defaultdict(lambda: {"v": 0.0, "n": 0, "sqs": set()})
    for g in groups.values():
        for r in kept_rows(g):
            name = (r["NM_DOADOR_RFB"] or r["NM_DOADOR"] or "").strip() or "Sem identificação"
            acc[name]["v"] += money(r["VR_RECEITA"])
            acc[name]["n"] += 1
            acc[name]["origem"] = r["DS_ORIGEM_RECEITA"].strip()
            acc[name]["sqs"].add(r["SQ_CANDIDATO"])
    return acc

LULA = "280002542548"
FLAVIO = "280002551544"
CDN = "https://d28e1s3vmdjm2r.cloudfront.net/Partidos2026/"

KNOWN = {
    "PARTIDO DOS TRABALHADORES - BRASIL - BR - NACIONAL": ("Partido dos Trabalhadores", "partido", "PT.jpg"),
    "PARTIDO LIBERAL (PL)": ("Partido Liberal", "partido", "PL.jpg"),
    "PARTIDO SOCIAL DEMOCRATICO - PSD DIRETORIO NACIONAL": ("PSD", "partido", "PSD.jpg"),
    "PARTIDO NOVO": ("Partido Novo", "partido", "NOVO.jpg"),
    "PARTIDO NOVO - MINAS GERAIS - MG - ESTADUAL": ("Novo de Minas", "partido", "NOVO.jpg"),
    "AVANTE DIRETORIO NACIONAL": ("Avante", "partido", "Avante.jpg"),
    "DEMOCRACIA CRISTA - BRASIL - BR - NACIONAL": ("Democracia Cristã", "partido", "DC.jpg"),
    "PARTIDO SOCIALISTA DOS TRABALHADORES UNIFICADO PSTU": ("PSTU", "partido", "PSTU.jpg"),
    "UNIDADE POPULAR": ("Unidade Popular", "partido", "UP.jpg"),
    "UM A MAIS SERVICOS DE TECNOLOGIA E CONSULTORIA LTDA": ("Um a Mais", "vaquinha", None),
    "QUEROAPOIAR.COM.BR LTDA": ("QueroApoiar", "vaquinha", None),
}

def person_names(name):
    raw = name.replace(".", " ").split()
    skip = {"da", "de", "do", "dos", "das", "e", "di"}
    suf = {"filho", "junior", "júnior", "neto", "sobrinho"}
    words = []
    for p in raw:
        if p.lower() in skip or p.upper() in {s.upper() for s in skip}:
            words.append(p.lower())
        elif p.isupper():
            words.append(p.capitalize())
        else:
            words.append(p)
    core = [w for w in words if w.lower() not in skip]
    if len(core) >= 3 and core[-1].lower() in suf:
        short = f"{core[0]} {core[-2]} {core[-1]}"
    elif len(core) >= 2:
        short = f"{core[0]} {core[-1]}"
    else:
        short = " ".join(words) or name
    full = " ".join(words)
    return short, full

def describe(raw):
    if raw in KNOWN:
        short, kind, logo = KNOWN[raw]
        return short, raw if short != raw else short, kind, (CDN + logo) if logo else None
    origem = ""
    short, full = person_names(raw)
    return short, full, "pessoa", None

def tile(raw, v, n, origem, sqs=None):
    short, full, kind, logo = describe(raw)
    if "própri" in origem.lower() or "propri" in origem.lower():
        kind = "proprio"
    elif "coletivo" in origem.lower() or kind == "vaquinha":
        kind = "vaquinha"
    elif "partido" in origem.lower() or kind == "partido":
        kind = "partido"
    tag = {"vaquinha": "vaquinha", "proprio": "próprio bolso", "partido": "partido"}.get(kind, "")
    out = {
        "nome": short,
        "completo": full if full != short else short,
        "v": round(v, 2),
        "n": n,
        "tag": tag,
        "logo": logo,
        "lista": [],
    }
    if sqs:
        out["_sqs"] = sorted(sqs)
    return out

def pack(acc, cut, fold_below):
    """Keep donors with v >= cut. The rest becomes one tile if fold_below is a label."""
    items = sorted(acc.items(), key=lambda kv: -kv[1]["v"])
    kept = []
    rest = []
    for name, d in items:
        if d["v"] >= cut:
            origem = d.get("origem") or ""
            kept.append(tile(name, d["v"], d["n"], origem, d.get("sqs")))
        else:
            rest.append((name, d))
    if rest and fold_below:
        rv = sum(d["v"] for _, d in rest)
        rn = sum(d["n"] for _, d in rest)
        sqs = set()
        for _, d in rest:
            sqs |= d.get("sqs") or set()
        kept.append({
            "nome": fold_below,
            "completo": f"{len(rest)} doadores abaixo do corte",
            "v": round(rv, 2),
            "n": len(rest),
            "tag": f"{len(rest)} doadores",
            "logo": None,
            "lista": [],
            "outros": True,
            "_sqs": sorted(sqs),
        })
    kept.sort(key=lambda t: -t["v"])
    return kept

lula_acc = donors_of([LULA])
flavio_acc = donors_of([FLAVIO])
demais_acc = donors_of([s for s in by_sq if s not in (LULA, FLAVIO)])

# Lula: the party is the tile. Everyone else is one strip, otherwise the names have no pixels.
lula_tiles = pack(lula_acc, cut=10**12, fold_below=None)
# cut above any value keeps nobody; do it explicitly
party_name = "PARTIDO DOS TRABALHADORES - BRASIL - BR - NACIONAL"
lula_tiles = []
rest = []
for name, d in lula_acc.items():
    if name == party_name:
        lula_tiles.append(tile(name, d["v"], d["n"], d.get("origem") or "", d.get("sqs")))
    else:
        rest.append((name, d))
rv = sum(d["v"] for _, d in rest)
lula_sqs = set()
for _, d in rest:
    lula_sqs |= d.get("sqs") or set()
lula_tiles.append({
    "nome": "Outros doadores",
    "completo": f"{len(rest)} doadores, fora o diretório nacional",
    "v": round(rv, 2),
    "n": len(rest),
    "tag": f"{len(rest)} doadores",
    "logo": None,
    "lista": [],
    "outros": True,
    "_sqs": sorted(lula_sqs),
})

flavio_tiles = pack(flavio_acc, cut=500_000, fold_below="Outros doadores")
demais_tiles = pack(demais_acc, cut=200_000, fold_below="Outros")

def total(tiles):
    return round(sum(t["v"] for t in tiles), 2)

def receipts_of(sq):
    groups = defaultdict(list)
    for r in by_sq[sq]:
        groups[r["SQ_RECEITA"]].append(r)
    out = []
    for g in groups.values():
        out.extend(kept_rows(g))
    return out

def brl_py(n):
    a = abs(n)
    if a >= 1_000_000:
        return "R$ " + f"{a/1_000_000:.1f}".replace(".", ",") + " mi"
    if a >= 1000:
        v = a / 1000
        d = 0 if v >= 100 else 1
        return "R$ " + f"{v:.{d}f}".replace(".", ",") + " mil"
    return "R$ " + f"{a:.0f}"

def norm_name(raw):
    return " ".join((raw or "").upper().split())

def display_person(raw):
    raw = (raw or "").strip()
    if not raw or raw.startswith("#") or "DIVULG" in raw.upper():
        return "Não divulgável"
    if raw in KNOWN:
        return KNOWN[raw][0]
    _short, full = person_names(raw)
    return full

def doc_digits(s):
    d = "".join(ch for ch in (s or "") if ch.isdigit())
    if len(d) in (11, 14) and any(ch != "0" for ch in d):
        return d
    return ""

def data_iso(s):
    s = (s or "").strip()
    if len(s) >= 10 and s[2] == "/" and s[5] == "/":
        return f"{s[6:10]}-{s[3:5]}-{s[0:2]}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return ""

def institucional(raw):
    raw = (raw or "").strip()
    if not raw or raw.startswith("#") or raw in KNOWN:
        return True
    u = norm_name(raw)
    if "DIVULG" in u or u in {"SEM IDENTIFICACAO", "NAO DIVULGAVEL", "NAO IDENTIFICADO"}:
        return True
    return any(k in u for k in ("PARTIDO", "FUNDO ESPECIAL", "FUNDO PARTID", "DIRETORIO", "DIRETÓRIO", "ELEICAO", "ELEIÇÃO"))

META = [
    {"sq": "280002542548", "urna": "Lula", "nome": "Luiz Inácio Lula da Silva", "partido": "PT", "numero": "13", "cor": "#EF4444", "foto": "Lula_da_Silva2.jpg"},
    {"sq": "280002551544", "urna": "Flávio Bolsonaro", "nome": "Flávio Nantes Bolsonaro", "partido": "PL", "numero": "22", "cor": "#266FE0", "foto": "Flavio_Bolsonaro2.jpg"},
    {"sq": "280002551932", "urna": "Ronaldo Caiado", "nome": "Ronaldo Ramos Caiado", "partido": "PSD", "numero": "55", "cor": "#184D9B", "foto": "Ronaldo_Caiado2.jpg"},
    {"sq": "280002539826", "urna": "Romeu Zema", "nome": "Romeu Zema Neto", "partido": "NOVO", "numero": "30", "cor": "#EA580C", "foto": "Romeu_Zema2.jpg"},
    {"sq": "280002551547", "urna": "Augusto Cury", "nome": "Augusto Jorge Cury", "partido": "AVANTE", "numero": "70", "cor": "#65A30D", "foto": "Augusto_Cury2.jpg"},
    {"sq": "280002540694", "urna": "Renan Santos", "nome": "Renan Antonio Ferreira dos Santos", "partido": "MISSÃO", "numero": "14", "cor": "#909EB1", "foto": "Renan_Santos2.jpg"},
    {"sq": "280002552484", "urna": "Clariana Barão", "nome": "Clariana Zacarkim Barão", "partido": "DC", "numero": "27", "cor": "#909EB1", "foto": "Clariana_Brandao2.jpg"},
    {"sq": "280002541457", "urna": "Hertz Dias", "nome": "Hertz da Conceição Dias", "partido": "PSTU", "numero": "16", "cor": "#909EB1", "foto": "Hertz_Dias2.jpg"},
    {"sq": "280002548139", "urna": "Wilson Grassi", "nome": "Wilson Grassi Júnior", "partido": "DEMOCRATA", "numero": "35", "cor": "#909EB1", "foto": "Wilson_Grassi2.jpg"},
    {"sq": "280002538811", "urna": "Samara Martins", "nome": "Samara Martins da Silva Feitosa", "partido": "UP", "numero": "80", "cor": "#909EB1", "foto": "Samara_Martins2.jpg"},
    {"sq": "280002551975", "urna": "Edmilson Costa", "nome": "Edmilson Silva Costa", "partido": "PCB", "numero": "21", "cor": "#909EB1", "foto": "Edmilson_Costa2.jpg"},
    {"sq": "280002553884", "urna": "Pablo Marçal", "nome": "Pablo Henrique Costa Marçal", "partido": "PRTB", "numero": "28", "cor": "#c98500", "foto": "Pablo_Marc%CC%A7al.jpg"},
    {"sq": "280002552487", "urna": "Rui Costa Pimenta", "nome": "Rui Costa Pimenta", "partido": "PCO", "numero": "29", "cor": "#909EB1", "foto": "Rui_Costa_Pimenta2.jpg"},
]
FOTO = "https://d28e1s3vmdjm2r.cloudfront.net/Candidatos2026/"
FICHA = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/BR/20322002026/{sq}/2026/BR"

rec_by_cand = {c["sq"]: receipts_of(c["sq"]) for c in META}
need = set()
for rows in rec_by_cand.values():
    for r in rows:
        ol = r["DS_ORIGEM_RECEITA"].lower()
        fonte = r["DS_FONTE_RECEITA"].upper()
        if "coletivo" in ol or "internet" in ol or ("partido" in ol and "OUTROS" in fonte):
            need.add(r["SQ_RECEITA"])

ori_by_sq = defaultdict(list)
with open(ORIGINARIO, encoding="latin-1", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if row["SQ_RECEITA"] in need:
            ori_by_sq[row["SQ_RECEITA"]].append(row)

def originarios(sq_receita):
    seen = set()
    out = []
    for o in ori_by_sq.get(sq_receita, []):
        nm = (o["NM_DOADOR_ORIGINARIO_RFB"] or o["NM_DOADOR_ORIGINARIO"] or "").strip()
        key = tuple(o.get(k, "") for k in (
            "NR_CPF_CNPJ_DOADOR_ORIGINARIO", "NM_DOADOR_ORIGINARIO", "NM_DOADOR_ORIGINARIO_RFB",
            "TP_DOADOR_ORIGINARIO", "SQ_RECEITA", "DT_RECEITA", "DS_RECEITA", "VR_RECEITA",
        ))
        if key in seen:
            continue
        seen.add(key)
        tp = (o.get("TP_DOADOR_ORIGINARIO") or "").strip().upper()
        doc = ""
        if tp != "J" and not institucional(nm):
            doc = doc_digits(o.get("NR_CPF_CNPJ_DOADOR_ORIGINARIO"))
        out.append((nm, money(o["VR_RECEITA"]), doc, data_iso(o.get("DT_RECEITA"))))
    return out

# Documento só como chave interna. Não entra no HTML.
tile_docs = defaultdict(set)

def build_doadores(c):
    sigla = c["partido"]
    pessoas = {}
    fundos = defaultdict(float)
    materiais = 0.0
    voo = 0.0
    resto_partido = 0.0
    vaquinhas = {}
    outros = defaultdict(float)
    outros_tag = {}

    def add_person(raw, v, field, proprio=False, doc="", quando="", como=""):
        key = norm_name(raw) or "SEM IDENTIFICACAO"
        if key not in pessoas:
            pessoas[key] = {"nome": display_person(raw), "direto": 0.0, "via": 0.0, "proprio": 0.0, "vaquinha": 0.0, "canais": [], "docs": set(), "movs": []}
        pessoas[key][field] += v
        if proprio:
            pessoas[key]["proprio"] += v
        if doc and not institucional(raw):
            pessoas[key]["docs"].add(doc)
        if v > 0:
            pessoas[key]["movs"].append({"dt": quando or "", "v": round(v, 2), "como": como or field})

    for r in rec_by_cand[c["sq"]]:
        v = money(r["VR_RECEITA"])
        if v <= 0:
            continue
        origem = r["DS_ORIGEM_RECEITA"].strip()
        ol = origem.lower()
        fonte = r["DS_FONTE_RECEITA"].strip().upper()
        donor = (r["NM_DOADOR_RFB"] or r["NM_DOADOR"] or "").strip()
        desc = (r["DS_RECEITA"] or "").lower()
        especie = (r["DS_ESPECIE_RECEITA"] or "").strip().lower()

        if "pessoas f" in ol:
            doc = "" if institucional(donor) else doc_digits(r.get("NR_CPF_CNPJ_DOADOR"))
            add_person(donor, v, "direto", doc=doc, quando=data_iso(r.get("DT_RECEITA")), como="direto")
            if donor and doc:
                tile_docs[(c["sq"], donor)].add(doc)
            continue
        if "própri" in ol or "propri" in ol:
            quem = donor or c["nome"]
            doc = "" if institucional(quem) else doc_digits(r.get("NR_CPF_CNPJ_DOADOR"))
            add_person(quem, v, "direto", proprio=True, doc=doc, quando=data_iso(r.get("DT_RECEITA")), como="próprio bolso")
            continue
        if "coletivo" in ol or "pela internet" in ol:
            plat = KNOWN[donor][0] if donor in KNOWN else (display_person(donor) if donor else "Financiamento coletivo")
            bucket = vaquinhas.setdefault(plat, {"v": 0.0, "pessoas": {}})
            bucket["v"] += v
            rec_dt = data_iso(r.get("DT_RECEITA"))
            for nm, ov, doc, dt in originarios(r["SQ_RECEITA"]):
                pk = norm_name(nm) or "NAO DIVULGAVEL"
                p = bucket["pessoas"].setdefault(pk, {"nome": display_person(nm), "v": 0.0, "docs": set(), "movs": []})
                p["v"] += ov
                if doc:
                    p["docs"].add(doc)
                if ov > 0:
                    p["movs"].append({"dt": dt or rec_dt, "v": round(ov, 2), "como": f"vaquinha · {plat}"})
            continue
        if "partido" in ol or "fundo especial" in ol or "fundo partid" in ol:
            if "FUNDO ESPECIAL" in fonte or "fundo especial" in ol:
                fundos["Fundo Especial"] += v
                continue
            if "FUNDO PARTID" in fonte or ol.startswith("fundo partid"):
                fundos["Fundo Partidário"] += v
                continue
            oris = originarios(r["SQ_RECEITA"])
            osum = sum(ov for _, ov, _, _ in oris)
            if oris and osum <= v + 0.05:
                rec_dt = data_iso(r.get("DT_RECEITA"))
                for nm, ov, doc, dt in oris:
                    add_person(nm, ov, "via", doc=doc, quando=dt or rec_dt, como=f"via {sigla}")
                if v - osum > 0.5:
                    resto_partido += v - osum
                continue
            if any(w in desc for w in ("voo", "aeronave", "learjet", "king air")):
                voo += v
                continue
            if "estimad" in especie:
                materiais += v
                continue
            resto_partido += v
            continue
        label = display_person(donor) if donor and not donor.startswith("#") else origem
        outros[label] += v
        if "candidato" in ol:
            outros_tag[label] = "outro candidato"
        elif "não identific" in ol or "nao identific" in ol:
            outros_tag[label] = "não identificada"

    rows = []
    doc_of = []

    def push(row, docs=None):
        rows.append(row)
        doc_of.append(set(docs or ()))

    for label, v in fundos.items():
        if v > 0:
            push({"nome": label, "v": round(v, 2), "tag": f"dinheiro público · {sigla}"})
    if voo > 0:
        push({"nome": "Horas de voo", "v": round(voo, 2), "tag": f"estimado · {sigla}"})
    if materiais > 0:
        push({"nome": "Material e cessões", "v": round(materiais, 2), "tag": f"estimado · {sigla}"})
    if resto_partido > 0:
        push({"nome": f"Repasse do {sigla}", "v": round(resto_partido, 2), "tag": "sem doador originário"})
    for plat, b in vaquinhas.items():
        ident = sum(p["v"] for p in b["pessoas"].values())
        if b["pessoas"] and ident <= b["v"] + 1:
            for pk, p in b["pessoas"].items():
                if pk not in pessoas:
                    pessoas[pk] = {"nome": p["nome"], "direto": 0.0, "via": 0.0, "proprio": 0.0, "vaquinha": 0.0, "canais": [], "docs": set(), "movs": []}
                pessoas[pk]["vaquinha"] += p["v"]
                pessoas[pk].setdefault("docs", set()).update(p.get("docs") or ())
                pessoas[pk].setdefault("movs", []).extend(p.get("movs") or [])
                if plat not in pessoas[pk]["canais"]:
                    pessoas[pk]["canais"].append(plat)
            gap = b["v"] - ident
            if gap > 0.5:
                push({"nome": plat, "v": round(gap, 2), "tag": "vaquinha · sem nome"})
        else:
            push({"nome": plat, "v": round(b["v"], 2), "tag": "vaquinha"})
    for p in pessoas.values():
        v = p["direto"] + p["via"] + p.get("vaquinha", 0.0)
        if v <= 0:
            continue
        tags = []
        so_proprio = p["proprio"] > 0 and abs(p["proprio"] - p["direto"]) < 0.05 and p["via"] == 0 and p.get("vaquinha", 0) == 0
        if so_proprio:
            tags.append("próprio bolso")
        else:
            if p["direto"] > 0 and p["via"] > 0:
                tags.append(brl_py(p["direto"]) + " direto")
                tags.append(brl_py(p["via"]) + f" via {sigla}")
            elif p["via"] > 0:
                tags.append(f"via {sigla}")
            if p["proprio"] > 0 and p["via"] == 0 and (p["direto"] > p["proprio"] + 0.05 or p.get("vaquinha", 0) > 0):
                tags.append("próprio bolso")
            if p.get("vaquinha", 0) > 0:
                canal = ", ".join(p.get("canais") or [])
                if p["direto"] > 0 or p["via"] > 0:
                    tags.append(brl_py(p["vaquinha"]) + " vaquinha" + (f" · {canal}" if canal else ""))
                else:
                    tags.append("vaquinha" + (f" · {canal}" if canal else ""))
        movs = list(p.get("movs") or [])
        row = {"nome": p["nome"], "v": round(v, 2), "tag": " · ".join(tags), "movs": movs}
        dts = [m.get("dt") or "" for m in movs if m.get("dt")]
        if dts:
            row["dt"] = max(dts)
        push(row, p.get("docs"))
    for label, v in outros.items():
        push({"nome": label, "v": round(v, 2), "tag": outros_tag.get(label, "")})
    paired = sorted(zip(rows, doc_of), key=lambda rd: -rd[0]["v"])
    return [r for r, _ in paired], [d for _, d in paired]

candidatos = []
pessoa_docs = []
for c in META:
    doadores, doc_of = build_doadores(c)
    receita = round(sum(money(r["VR_RECEITA"]) for r in rec_by_cand[c["sq"]]), 2)
    soma = round(sum(d["v"] for d in doadores), 2)
    if abs(soma - receita) > 1:
        raise SystemExit(f"soma {c['urna']} {soma} != {receita}")
    candidatos.append({
        "sq": c["sq"],
        "urna": c["urna"],
        "nome": c["nome"],
        "partido": c["partido"],
        "numero": c["numero"],
        "cor": c["cor"],
        "foto": FOTO + c["foto"],
        "total": receita,
        "url": FICHA.format(sq=c["sq"]),
        "doadores": doadores,
    })
    pessoa_docs.append(doc_of)
    tops = ", ".join(f"{d['nome'][:28]} {d['v']/1e6:.2f}" for d in doadores[:5])
    print(f"DET {c['urna']:20} {receita/1e6:8.2f}  linhas={len(doadores):4}  {tops}")

doc_to_sqs = defaultdict(set)
for cand, doc_of in zip(candidatos, pessoa_docs):
    for docs in doc_of:
        for doc in docs:
            doc_to_sqs[doc].add(cand["sq"])
crossed_docs = {doc for doc, sqs in doc_to_sqs.items() if len(sqs) >= 2}
urna_of = {c["sq"]: c["urna"] for c in META}
order = [c["sq"] for c in META]

def outras_urnas(docs, skip):
    sqs = set()
    for doc in docs:
        if doc in crossed_docs:
            sqs |= doc_to_sqs[doc]
    sqs -= skip
    return [urna_of[sq] for sq in order if sq in sqs]

parent = {}

def find(x):
    parent.setdefault(x, x)
    if parent[x] != x:
        parent[x] = find(parent[x])
    return parent[x]

def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

members = []
for cand, doc_of in zip(candidatos, pessoa_docs):
    for row, docs in zip(cand["doadores"], doc_of):
        cds = [d for d in docs if d in crossed_docs]
        if not cds:
            continue
        if len(cds) > 1:
            print(f"DOC-DUP {cand['urna']} {row['nome']} n={len(cds)}")
        for d in cds[1:]:
            union(cds[0], d)
        locais = []
        for m in row.pop("movs", []) or []:
            locais.append({"dt": m.get("dt") or "", "v": m["v"], "como": m.get("como") or "", "urna": cand["urna"], "sq": cand["sq"]})
        urnas = outras_urnas(docs, {cand["sq"]})
        if urnas:
            row["tambem"] = urnas
        members.append((cand, row, cds, locais))

grupos = defaultdict(list)
for cand, row, cds, locais in members:
    grupos[find(cds[0])].append((cand, row, locais))

def compactar(movs):
    acc = {}
    for m in movs:
        chave = (m["dt"], m["urna"], m["sq"], m["como"])
        slot = acc.setdefault(chave, {"dt": m["dt"], "urna": m["urna"], "sq": m["sq"], "como": m["como"], "v": 0.0, "n": 0})
        slot["v"] += m["v"]
        slot["n"] += 1
    out = []
    for s in acc.values():
        item = {"dt": s["dt"], "urna": s["urna"], "sq": s["sq"], "v": round(s["v"], 2), "como": s["como"]}
        if s["n"] > 1:
            item["n"] = s["n"]
        out.append(item)
    out.sort(key=lambda m: (m["dt"] or "9999", -m["v"], m["urna"]))
    return out

cruzados = []
for items in grupos.values():
    nome = sorted(items, key=lambda it: (-it[1]["v"], -len(it[1]["nome"])))[0][1]["nome"]
    por_sq = {}
    brutos = []
    for cand, row, locais in items:
        brutos.extend(locais)
        slot = por_sq.setdefault(cand["sq"], {"urna": cand["urna"], "sq": cand["sq"], "v": 0.0, "tag": "", "nome": row["nome"], "_mv": -1.0})
        slot["v"] += row["v"]
        if row["v"] >= slot["_mv"]:
            slot["_mv"] = row["v"]
            slot["tag"] = row.get("tag") or ""
            slot["nome"] = row["nome"]
    camps = [{"urna": s["urna"], "sq": s["sq"], "v": round(s["v"], 2), "tag": s["tag"], "nome": s["nome"]} for s in por_sq.values()]
    if len(camps) < 2:
        raise SystemExit(f"cruzado numa campanha só: {nome}")
    camps.sort(key=lambda x: -x["v"])
    movs = compactar(brutos)
    total_v = round(sum(x["v"] for x in camps), 2)
    soma_movs = round(sum(m["v"] for m in movs), 2)
    if abs(soma_movs - total_v) > 1:
        raise SystemExit(f"movs {nome} {soma_movs} != {total_v}")
    for _cand, row, _locais in items:
        if row.get("tambem"):
            row["movs"] = movs
    item = {"nome": nome, "v": total_v, "n": len(camps), "campanhas": camps, "movs": movs}
    dts = [m["dt"] for m in movs if m.get("dt")]
    if dts:
        item["dt"] = max(dts)
    cruzados.append(item)
cruzados.sort(key=lambda r: (-r["v"], r["nome"]))
for cand in candidatos:
    for row in cand["doadores"]:
        if not row.get("tambem"):
            row.pop("movs", None)

def mark_tiles(tiles, sqs, label):
    sq_set = set(sqs)
    idx = defaultdict(set)
    for (sq, raw), docs in tile_docs.items():
        if sq not in sq_set or not docs:
            continue
        short, full, kind, _logo = describe(raw)
        if kind != "pessoa":
            continue
        idx[full if full != short else short] |= docs
    for t in tiles:
        if t.get("outros"):
            continue
        docs = idx.get(t.get("completo")) or set()
        crossed = [d for d in docs if d in crossed_docs]
        if not crossed:
            continue
        all_sqs = set()
        for d in crossed:
            all_sqs |= doc_to_sqs[d]
        outside = all_sqs - sq_set
        inside = all_sqs & sq_set
        show = outside if outside else (inside if len(inside) >= 2 else set())
        if len(sqs) == 1:
            show = outside
        if not show:
            continue
        t["tambem"] = [urna_of[sq] for sq in order if sq in show]
        print(f"TILE {label} {t['nome']} {t['tambem']}")

mark_tiles(lula_tiles, [LULA], "lula")
mark_tiles(flavio_tiles, [FLAVIO], "flavio")
mark_tiles(demais_tiles, [c["sq"] for c in META if c["sq"] not in (LULA, FLAVIO)], "demais")

def pintar_partido(tiles, misturado):
    por_sq = {c["sq"]: c for c in META}
    for t in tiles:
        sqs = t.pop("_sqs", [])
        if not misturado or len(sqs) != 1:
            continue
        meta = por_sq.get(sqs[0])
        if not meta or meta["cor"].lower() == "#909eb1":
            continue
        t["cor"] = meta["cor"]
        t["partido"] = meta["partido"]
        t["sq"] = meta["sq"]

pintar_partido(lula_tiles, False)
pintar_partido(flavio_tiles, False)
pintar_partido(demais_tiles, True)
for t in lula_tiles + flavio_tiles + demais_tiles:
    if "_sqs" in t:
        raise SystemExit("sobrou _sqs em " + t.get("nome", ""))

import unicodedata

def fold(s):
    s = unicodedata.normalize("NFD", (s or "").upper())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

for needle in (
    "ERASMO CARLOS BATTISTELLA",
    "WALDEMAR VERDI",
    "HELIO SEIBEL",
    "SALO DAVI SEIBEL",
    "RODRIGO DE ALMEIDA PIZZINATTO",
    "PAULA MARCELA",
):
    if not any(needle in fold(x["nome"]) for x in cruzados):
        raise SystemExit("falta cruzado " + needle)

cruz_total = round(sum(x["v"] for x in cruzados), 2)
print(f"CRUZADOS {len(cruzados)}  R$ {cruz_total:,.2f}")
for x in cruzados[:8]:
    bits = ", ".join(f"{k['urna']} {k['v']:.0f} {k['tag']}" for k in x["campanhas"])
    datas = " | ".join(f"{m['dt']} {m['urna']} {m['v']:.0f} {m['como']}" for m in x["movs"])
    print(f"  {x['v']:12.2f}  n={x['n']}  {x['nome']}  {bits}")
    print(f"    {datas}")
for cand in candidatos:
    n = sum(1 for d in cand["doadores"] if d.get("tambem"))
    if n:
        print(f"  na ficha {cand['urna']:20} {n}")

def scrub(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in {"docs", "cpf", "doc", "_mv"}:
                raise SystemExit(f"vazou {k} em {path}")
            scrub(v, path + "." + k)
    elif isinstance(o, (list, tuple)):
        for v in o:
            scrub(v, path)
    elif isinstance(o, set):
        raise SystemExit(f"set no payload {path}")

data = {
    "gerado": "17/10/2026",
    "hora": "04:05",
    "lula": {"sq": "280002542548", "rotulo": "Lula · PT", "cor": "#C4161C", "url": "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/BR/20322002026/280002542548/2026/BR", "tiles": lula_tiles, "total": total(lula_tiles)},
    "flavio": {"sq": "280002551544", "rotulo": "Flávio Bolsonaro · PL", "cor": "#266FE0", "url": "https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/BR/20322002026/280002551544/2026/BR", "tiles": flavio_tiles, "total": total(flavio_tiles)},
    "demais": {"rotulo": "Demais candidaturas", "cor": "#3E4654", "url": None, "tiles": demais_tiles, "total": total(demais_tiles)},
    "candidatos": candidatos,
    "cruzados": cruzados,
    "cruzadosTotal": cruz_total,
}
scrub(data)
grand = data["lula"]["total"] + data["flavio"]["total"] + data["demais"]["total"]
data["grand"] = grand
print("LULA", data["lula"]["total"] / 1e6)
for t in lula_tiles:
    print(f"  {t['v']/1e6:8.2f}  {t['nome']}  lista={len(t['lista'])}")
print("FLAVIO", data["flavio"]["total"] / 1e6)
for t in flavio_tiles:
    print(f"  {t['v']/1e6:8.2f}  {t['nome']}")
print("DEMAIS", data["demais"]["total"] / 1e6)
for t in demais_tiles:
    print(f"  {t['v']/1e6:8.2f}  {t['nome']}  {t.get('partido', '')}")
print("GRAND", grand / 1e6)

html = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Quem põe o dinheiro — campanha presidencial 2026 · DecideBrasil</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet" />
<style>
  :root { --bg:#f0f0f0; --text:#3c3c3c; --muted:#8a8a8a; --blue:#2150e8; --line:#eeeef0; --edge:#e0e0e0; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font-family:"Hanken Grotesk", system-ui, sans-serif; -webkit-font-smoothing:antialiased; }
  .page { max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }
  .brand { display:flex; align-items:baseline; gap:12px; margin:0 4px 14px; }
  .brand b { color:var(--blue); font-weight:800; font-size:15px; letter-spacing:-0.2px; }
  .brand span { color:var(--muted); font-size:14px; }
  .card { background:#fff; border-radius:12px; box-shadow:0px 3.54px 13.88px 2.78px rgba(0,0,0,0.18); overflow:hidden; }
  .head { padding: 22px 22px 0; }
  h1 { margin:0; font-size:30px; line-height:1.15; font-weight:700; letter-spacing:-0.3px; }
  .sub { margin:8px 0 0; max-width:680px; color:var(--muted); font-size:15px; line-height:1.4; }
  .key { display:flex; flex-wrap:wrap; gap:8px 18px; margin:14px 0 14px; }
  .key a, .key span { display:inline-flex; align-items:center; gap:8px; color:var(--text); text-decoration:none; font-size:14px; font-weight:600; }
  .key a:hover { color:var(--blue); }
  .sw { width:12px; height:12px; border-radius:3px; display:inline-block; }
  .key b { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:700; letter-spacing:-0.3px; }
  .cands { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 0; }
  .cand { display:inline-flex; align-items:center; gap:8px; border:1px solid var(--edge); background:#fff; color:var(--text); border-radius:999px; padding:4px 12px 4px 4px; cursor:pointer; font: inherit; font-weight:600; font-size:14px; }
  .cand img, .cand .ini { width:32px; height:32px; border-radius:50%; object-fit:cover; border:2px solid #ddd; background:#eee; }
  .cand .ini { display:inline-flex; align-items:center; justify-content:center; font-size:11px; font-weight:800; color:#fff; }
  .cand b { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:500; font-size:12px; letter-spacing:-0.3px; color:var(--muted); }
  .cand .sig { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:11px; font-weight:700; letter-spacing:0.2px; }
  .cand.on { border-color: var(--ring, var(--blue)); box-shadow: 0 0 0 1px var(--ring, var(--blue)); }
  .key button.keybtn { border:0; background:transparent; padding:0; cursor:pointer; font:inherit; }
  .board { display:flex; height:620px; gap:6px; background:#fff; }
  .lula, .flavio { cursor:pointer; }
  .lula { flex:108.34 1 0; position:relative; min-width:0; }
  .right { flex:119.23 1 0; display:flex; flex-direction:column; gap:8px; min-width:0; }
  .flavio { flex:88.95 1 0; position:relative; min-height:0; }
  .demais { flex:30.28 1 0; position:relative; min-height:0; }
  .tile { position:absolute; overflow:hidden; color:#fff; display:flex; flex-direction:column; justify-content:flex-start; padding:10px 12px; text-shadow:0 1px 1px rgba(0,0,0,.28); }
  .tile .cruzbadge { text-shadow:none; }
  .tile .amt { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:700; letter-spacing:-0.5px; line-height:1; white-space:nowrap; }
  .tile .nm { font-weight:700; letter-spacing:-0.2px; line-height:1.15; margin-top:4px; }
  .tile .tag { margin-top:2px; font-size:11px; font-weight:600; opacity:.85; white-space:nowrap; }
  .tile.rowline { flex-direction:row; align-items:center; gap:8px; padding:0 10px; }
  .tile.rowline .nm { margin-top:0; font-weight:600; }
  .tile img.logo { position:absolute; right:10px; bottom:10px; width:36px; height:36px; object-fit:contain; background:#fff; border-radius:50%; border:1px solid rgba(255,255,255,.7); }
  .tile.dim { background-image: repeating-linear-gradient(-45deg, transparent, transparent 6px, rgba(255,255,255,.06) 6px, rgba(255,255,255,.06) 7px); }
  .tip { position:fixed; z-index:5; max-width:280px; background:#fff; color:var(--text); border-radius:10px; box-shadow:0 8px 28px rgba(0,0,0,.18); padding:10px 12px; pointer-events:none; }
  .tip[hidden] { display:none; }
  .tip strong { display:block; font-size:14px; }
  .tip .money { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:700; margin-top:2px; }
  .tip ul { margin:8px 0 0; padding:0; list-style:none; }
  .tip li { display:flex; justify-content:space-between; gap:12px; font-size:12px; padding:2px 0; }
  .tip li b { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:500; }
  .detail { margin-top:18px; }
  .detail[hidden] { display:none; }
  .dhead { display:grid; grid-template-columns: 72px 1fr auto; gap:14px; align-items:center; padding:20px 22px 0; }
  .dhead img, .dhead .ini { width:68px; height:68px; border-radius:50%; object-fit:cover; border:3px solid #ddd; background:#eee; }
  .dhead .ini { display:flex; align-items:center; justify-content:center; color:#fff; font-weight:800; font-size:18px; }
  .kicker { margin:0; color:var(--muted); font-size:13px; font-weight:600; }
  .dhead h2 { margin:1px 0 0; font-size:28px; line-height:1.05; letter-spacing:-0.4px; font-weight:700; }
  .civil { margin:3px 0 0; color:var(--muted); font-size:14px; }
  .meta { margin:2px 0 0; color:var(--muted); font-size:13px; }
  .meta a { color:var(--blue); text-decoration:none; font-weight:600; }
  .meta a:hover { text-decoration:underline; }
  .metric .k { margin:0; color:var(--muted); font-size:12px; font-weight:500; text-align:right; }
  .metric .v { margin:1px 0 0; font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:700; font-size:28px; letter-spacing:-0.6px; line-height:1.1; text-align:right; }
  .tools { display:flex; align-items:center; gap:12px; padding:14px 22px 8px; }
  .dnote { margin:0; flex:1; color:var(--muted); font-size:13px; line-height:1.35; }
  .find { width:220px; height:36px; margin:0; border:1px solid var(--edge); border-radius:999px; padding:0 14px; font:inherit; font-size:14px; color:var(--text); background:#fff; }
  .find:focus { outline:2px solid var(--blue); border-color:transparent; }
  .x { border:0; background:var(--bg); color:var(--text); border-radius:999px; height:36px; padding:0 14px; cursor:pointer; font:inherit; font-weight:700; font-size:13px; }
  .x:hover { background:#e6e6e6; }
  .row { display:grid; grid-template-columns: 36px 40px minmax(180px,1fr) minmax(168px, 200px) 168px; gap:8px 14px; align-items:center; padding:13px 22px; border-top:1px solid var(--line); }
  .row.top { padding-top:16px; padding-bottom:16px; }
  .rk { font-family:"JetBrains Mono", ui-monospace, monospace; color:var(--muted); font-size:16px; font-weight:500; }
  .row.top .rk { color:var(--text); font-weight:700; }
  .mark { width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:800; font-size:13px; letter-spacing:-0.3px; }
  .mark.cruz { box-shadow: 0 0 0 2px #fff, 0 0 0 4px #2150e8; }
  .row.cruz { box-shadow: inset 3px 0 0 #2150e8; cursor: pointer; }
  .row.cruz:hover { background: #f4f7ff; }
  .movs { max-height: 280px; overflow: auto; margin: 0 22px 14px 112px; background: #f4f6fb; border-radius: 10px; padding: 4px 16px 6px; }
  .mrow { display: grid; grid-template-columns: 96px minmax(120px, 1fr) minmax(100px, auto) auto; gap: 8px 16px; align-items: center; padding: 9px 0; border-bottom: 1px solid #e4e7f0; font-size: 14px; }
  .mrow:last-child { border-bottom: 0; }
  .mdt, .mrow b { font-family: "JetBrains Mono", ui-monospace, monospace; }
  .mdt { font-weight: 500; }
  .mrow b { font-weight: 700; text-align: right; }
  .mcomo { color: var(--muted); }
  .catpill { display:inline-block; margin-right:6px; padding:1px 7px 2px; border-radius:999px; background:#2150e8; color:#fff; font-family:"JetBrains Mono", ui-monospace, monospace; font-size:10px; font-weight:700; letter-spacing:0.3px; vertical-align:1px; }
  .nm { font-size:18px; font-weight:700; letter-spacing:-0.3px; line-height:1.15; }
  .tag { color:var(--muted); font-size:13px; font-weight:500; margin-top:2px; }
  .x.filtro.on { background:#2150e8; color:#fff; }
  .filters { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:2px 22px 14px; }
  .flab { color:var(--muted); font-size:12px; font-weight:700; }
  .sort { display:inline-flex; background:var(--bg); border-radius:999px; padding:3px; gap:2px; }
  .sort button { border:0; background:transparent; color:var(--muted); height:30px; padding:0 12px; border-radius:999px; cursor:pointer; font:inherit; font-weight:700; font-size:13px; }
  .sort button.on { background:#fff; color:var(--text); box-shadow:0 1px 2px rgba(0,0,0,.12); }
  .x.part { border:1px solid var(--edge); background:#fff; display:inline-flex; align-items:center; gap:6px; }
  .x.part.on { border-color:transparent; }
  .pdot { width:8px; height:8px; border-radius:50%; display:inline-block; vertical-align:middle; flex:none; }
  .fmeta { margin:0; padding:0 22px 10px; color:var(--muted); font-family:"JetBrains Mono", ui-monospace, monospace; font-size:12px; }
  .murna { display:inline-flex; align-items:center; gap:6px; }
  .camp { border:0; background:transparent; color:#2150e8; font:inherit; font-weight:600; font-size:13px; padding:0; cursor:pointer; }
  .camp:hover { text-decoration:underline; }
  .tile .cruzbadge { position:absolute; top:6px; right:8px; background:#fff; color:#2150e8; font-family:"JetBrains Mono", ui-monospace, monospace; font-size:10px; font-weight:700; border-radius:999px; padding:1px 5px; line-height:1.4; }
  .share { display:flex; align-items:center; gap:8px; }
  .pct { font-family:"JetBrains Mono", ui-monospace, monospace; font-size:13px; font-weight:500; min-width:52px; text-align:right; flex:none; white-space:nowrap; }
  .track { flex:1; height:6px; border-radius:99px; background:#eee; overflow:hidden; }
  .track i { display:block; height:100%; border-radius:99px; min-width:4px; }
  .amt { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:700; font-size:20px; letter-spacing:-0.5px; text-align:right; white-space:nowrap; }
  .row.top .amt { font-size:26px; }
  .vaqbtn { display:inline-block; margin-top:4px; border:0; background:transparent; color:var(--blue); cursor:pointer; font:inherit; font-weight:700; font-size:13px; padding:0; }
  .pessoas { max-height:280px; overflow:auto; margin:0 22px 14px 112px; background:#f7f7f7; border-radius:10px; padding:6px 14px; }
  .pessoas .prow { display:flex; justify-content:space-between; gap:12px; padding:6px 0; font-size:14px; border-bottom:1px solid #eee; }
  .pessoas .prow:last-child { border-bottom:0; }
  .pessoas .prow b { font-family:"JetBrains Mono", ui-monospace, monospace; font-weight:500; }
  .more { display:block; width:calc(100% - 44px); margin:8px 22px 18px; border:0; background:#f4f4f4; color:var(--text); border-radius:999px; padding:11px 16px; cursor:pointer; font:inherit; font-weight:700; font-size:14px; }
  .more:hover { background:#ececec; }
  .empty { color:var(--muted); padding:8px 22px 22px; }
  footer { margin:14px 6px 0; color:var(--muted); font-size:12px; line-height:1.45; }
  footer a { color:var(--muted); }
  @media (max-width: 800px) {
    h1 { font-size:22px; }
    .dhead { grid-template-columns: 56px 1fr; }
    .dhead img, .dhead .ini { width:56px; height:56px; }
    .metric { grid-column: 1 / -1; }
    .metric .k, .metric .v { text-align:left; }
    .tools { flex-wrap:wrap; }
    .find { flex:1; width:auto; }
    .row { grid-template-columns: 24px 36px 1fr auto; grid-template-areas: "rk mark name amt" "share share share share"; }
    .rk { grid-area:rk; font-size:13px; }
    .mark { grid-area:mark; width:36px; height:36px; }
    .id { grid-area:name; }
    .nm { font-size:16px; }
    .share { grid-area:share; }
    .amt { grid-area:amt; font-size:16px; }
    .row.top .amt { font-size:20px; }
    .pessoas, .movs { margin-left:22px; }
    .mrow { grid-template-columns: 88px 1fr auto; }
    .mcomo { grid-column: 1 / -1; margin-top: -6px; }
    .board { flex-direction:column; height:auto; }
    .lula { height:420px; flex:none; }
    .right { flex:none; height:520px; }
  }
</style>
</head>
<body>
<div class="page">
  <p class="brand"><b>DecideBrasil</b><span>Eleições 2026 · Presidente</span></p>
  <article class="card">
    <header class="head">
      <h1>O PT declara R$ 105 mi para Lula.<br>No PL, pessoas físicas entram com R$ 21 mi.</h1>
      <p class="sub">A área é o valor declarado ao TSE. Cada retângulo é um doador. Nas demais candidaturas, a cor é a do partido. Clique para filtrar, ordenar e ver quem doou a mais de uma campanha.</p>
      <div class="cands" id="cands"></div>
      <div class="key" id="key"></div>
    </header>
    <div class="board" id="board">
      <div class="lula" id="lula"></div>
      <div class="right">
        <div class="flavio" id="flavio"></div>
        <div class="demais" id="demais"></div>
      </div>
    </div>
  </article>
  <article class="card detail" id="detail" hidden></article>
  <footer id="fonte"></footer>
</div>
<div class="tip" id="tip" hidden></div>
<script id="dados" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("dados").textContent);
const porUrna = {};
const porPartido = {};
DATA.candidatos.forEach(c => {
  porUrna[c.urna] = c;
  if (!porPartido[c.partido]) porPartido[c.partido] = c;
});

function brl(n) {
  const a = Math.abs(n);
  if (a >= 1e6) return "R$ " + (a / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " mi";
  if (a >= 1000) {
    const v = a / 1000;
    const d = (v >= 100 || Math.abs(v - Math.round(v)) < 0.05) ? 0 : 1;
    return "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }) + " mil";
  }
  return "R$ " + a.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}
function brlCheio(n) {
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function brlFit(n, tw) {
  if (tw >= 118) return brl(n);
  if (n >= 1e6) return (n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
  if (n >= 1000) return Math.round(n / 1000).toLocaleString("pt-BR") + " mil";
  return brl(n);
}

function worst(row, w) {
  const s = row.reduce((a, b) => a + b, 0);
  const rmax = Math.max(...row), rmin = Math.min(...row);
  return Math.max((w * w * rmax) / (s * s), (s * s) / (w * w * rmin));
}
function squarify(weights, x, y, dx, dy) {
  const area = dx * dy;
  const total = weights.reduce((a, b) => a + b, 0) || 1;
  const sizes = weights.map(w => w / total * area);
  const out = [];
  function layout(row, x, y, dx, dy) {
    const covered = row.reduce((a, b) => a + b, 0);
    const rects = [];
    if (dx >= dy) {
      const width = covered / dy;
      let y0 = y;
      row.forEach(s => {
        const h = s / width;
        rects.push({ x, y: y0, w: width, h });
        y0 += h;
      });
      return [rects, x + width, y, dx - width, dy];
    }
    const height = covered / dx;
    let x0 = x;
    row.forEach(s => {
      const w = s / height;
      rects.push({ x: x0, y, w, h: height });
      x0 += w;
    });
    return [rects, x, y + height, dx, dy - height];
  }
  function rec(sizes, x, y, dx, dy) {
    if (!sizes.length || dx <= 0 || dy <= 0) return;
    if (sizes.length === 1) {
      out.push({ x, y, w: dx, h: dy });
      return;
    }
    const w = Math.min(dx, dy);
    let i = 1;
    const row = [sizes[0]];
    while (i < sizes.length && worst(row.concat([sizes[i]]), w) <= worst(row, w)) {
      row.push(sizes[i]);
      i++;
    }
    const [rects, nx, ny, ndx, ndy] = layout(row, x, y, dx, dy);
    rects.forEach(r => out.push(r));
    rec(sizes.slice(i), nx, ny, ndx, ndy);
  }
  rec(sizes, x, y, dx, dy);
  return out;
}

const tip = document.getElementById("tip");
function showTip(e, t) {
  const linhas = (t.lista || []).map(d =>
    "<li><span>" + d.nome + (d.tag ? " · " + d.tag : "") + "</span><b>" + brl(d.v) + "</b></li>"
  ).join("");
  const cat = tambemTxt(t.tambem);
  const partidoLinha = t.partido && t.nome !== t.partido ? "<div class='tag'>" + esc(t.partido) + "</div>" : "";
  tip.innerHTML = "<strong>" + t.completo + "</strong><div class='money'>" + brlCheio(t.v) + "</div>"
    + partidoLinha
    + (cat ? "<div class='tag'>" + esc(cat) + "</div>" : "")
    + (t.tag && !t.outros ? "<div class='tag'>" + esc(t.tag) + "</div>" : "")
    + (t.outros ? "<div class='tag'>Lista completa na ficha do candidato.</div>" : "")
    + (linhas ? "<ul>" + linhas + "</ul>" : "");
  tip.hidden = false;
  const pad = 14;
  let x = e.clientX + pad, y = e.clientY + pad;
  tip.style.left = x + "px";
  tip.style.top = y + "px";
  const r = tip.getBoundingClientRect();
  if (r.right > window.innerWidth - 8) tip.style.left = (e.clientX - r.width - pad) + "px";
  if (r.bottom > window.innerHeight - 8) tip.style.top = (e.clientY - r.height - pad) + "px";
}

function draw(id, group) {
  const box = document.getElementById(id);
  box.innerHTML = "";
  const w = box.clientWidth, h = box.clientHeight;
  if (w < 20 || h < 20) return;
  const tiles = group.tiles;
  const rects = squarify(tiles.map(t => t.v), 0, 0, w, h);
  const pad = 3;
  tiles.forEach((t, i) => {
    const r = rects[i];
    const el = document.createElement("div");
    el.className = "tile" + (t.outros ? " dim" : "");
    const bg = t.cor || group.cor;
    el.style.background = bg;
    const ink = contraste(bg);
    el.style.color = ink;
    if (ink !== "#fff") el.style.textShadow = "none";
    if (t.sq) el.style.cursor = "pointer";
    const x = r.x + pad, y = r.y + pad;
    const tw = Math.max(0, r.w - pad * 2), th = Math.max(0, r.h - pad * 2);
    el.style.left = x + "px";
    el.style.top = y + "px";
    el.style.width = tw + "px";
    el.style.height = th + "px";
    el.setAttribute("aria-label", t.completo + " " + brlCheio(t.v));
    const faixa = th < 34 && tw > 150;
    const cat = tambemTxt(t.tambem);
    const tagLine = t.tag || cat;
    let html = "";
    if (faixa) {
      el.classList.add("rowline");
      html = "<div class='amt' style='font-size:13px'>" + brl(t.v) + "</div>"
        + "<div class='nm' style='font-size:13px'>" + t.nome + "</div>"
        + (tagLine ? "<div class='tag' style='margin:0'>" + tagLine + "</div>" : "");
    } else {
      const amtSize = Math.max(11, Math.min(48, Math.floor(tw / 6.5)));
      const nmSize = Math.max(11, Math.min(22, Math.floor(tw / 11)));
      if (t.logo && tw > 220 && th > 160) html += "<img class='logo' alt='' src='" + t.logo + "'>";
      if (th >= 20 && tw >= 36) {
        html += "<div class='amt' style='font-size:" + amtSize + "px'>" + brlFit(t.v, tw) + "</div>";
      }
      if (th >= 52 && tw >= 64) {
        html += "<div class='nm' style='font-size:" + nmSize + "px'>" + t.nome + "</div>";
        if (tagLine && th >= 78 && tw >= 90) html += "<div class='tag'>" + tagLine + "</div>";
        else if (cat && tw >= 54 && th >= 32) html += "<span class='cruzbadge'>2+</span>";
      } else if (cat && tw >= 54 && th >= 32) {
        html += "<span class='cruzbadge'>2+</span>";
      }
    }
    el.innerHTML = html;
    el.addEventListener("pointerenter", e => showTip(e, t));
    el.addEventListener("pointermove", e => showTip(e, t));
    el.addEventListener("pointerleave", () => { tip.hidden = true; });
    if (t.sq) el.addEventListener("click", (e) => {
      e.stopPropagation();
      tip.hidden = true;
      openCand(t.sq, true);
    });
    const img = el.querySelector("img");
    if (img) img.addEventListener("error", () => img.remove());
    box.appendChild(el);
  });
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}
function iniciais(nome) {
  return nome.split(/\s+/).filter(Boolean).slice(0, 2).map(p => p[0]).join("").toUpperCase();
}
function candBy(sq) {
  return DATA.candidatos.find(c => c.sq === sq);
}

let aberto = null;
let busca = "";
let soCruzados = false;
let so3 = false;
let ordem = "valor";
let tipo = "";
let partidosSel = new Set();
let movAberto = "";

function renderCands() {
  const box = document.getElementById("cands");
  const cruzOn = aberto === "cruzados" ? " on" : "";
  box.innerHTML = DATA.candidatos.map(c => {
    const on = aberto === c.sq ? " on" : "";
    return "<button type='button' class='cand" + on + "' data-sq='" + c.sq + "' style='--ring:" + c.cor + "'>"
      + "<img alt='' style='border-color:" + c.cor + "' src='" + esc(c.foto) + "'>"
      + "<span>" + esc(c.urna) + "</span>"
      + "<span class='sig' style='color:" + c.cor + "'>" + esc(c.partido) + "</span>"
      + "<b>" + brl(c.total) + "</b></button>";
  }).join("")
    + "<button type='button' class='cand" + cruzOn + "' data-sq='cruzados' style='--ring:#2150e8'>"
    + "<span class='ini' style='background:#2150e8;border-color:#2150e8'>2+</span>"
    + "<span>Cruzados</span><b>" + brl(DATA.cruzadosTotal || 0) + "</b></button>";
  box.querySelectorAll("img").forEach(img => {
    img.addEventListener("error", () => {
      const c = candBy(img.closest("button").dataset.sq);
      const s = document.createElement("span");
      s.className = "ini";
      s.style.background = c.cor;
      s.textContent = iniciais(c.urna);
      img.replaceWith(s);
    });
  });
  box.querySelectorAll("button").forEach(b => {
    b.addEventListener("click", () => {
      if (aberto === b.dataset.sq) fechar();
      else openCand(b.dataset.sq, true);
    });
  });
}

function tambemTxt(xs) {
  if (!xs || !xs.length) return "";
  if (xs.length === 1) return "também em " + xs[0];
  return "também em " + xs.slice(0, -1).join(", ") + " e " + xs[xs.length - 1];
}
function tagDe(d) {
  const bits = [];
  const cat = tambemTxt(d.tambem);
  if (cat) bits.push(cat);
  if (d.tag) bits.push(d.tag);
  if (d.n) bits.push(d.n.toLocaleString("pt-BR") + " pessoas");
  if (d.pessoas && d.pessoas.length && brl(d.identificado) !== brl(d.v)) {
    bits.push(brl(d.identificado) + " com nome");
  }
  return bits.join(" · ");
}
function pctLabel(p) {
  if (!(p > 0)) return "0%";
  let digits = 0;
  if (p < 10) digits = 1;
  if (p < 1) digits = 2;
  if (p < 0.01) digits = 3;
  if (p < 0.001) digits = Math.min(6, Math.ceil(-Math.log10(p)));
  return p.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits }) + "%";
}
function marca(d, cor) {
  const tag = d.tag || "";
  let bg = "#909EB1";
  let label = iniciais(d.nome);
  if (tag.indexOf("dinheiro público") >= 0) { bg = cor; label = "R$"; }
  else if (tag.indexOf("vaquinha") >= 0) { bg = "#2150e8"; label = "V"; }
  else if (tag.indexOf("estimado") >= 0 || tag.indexOf("sem doador") >= 0) { bg = cor; label = iniciais(d.nome); }
  else if (tag.indexOf("via ") >= 0 || tag.indexOf("próprio") >= 0) bg = cor;
  const cruz = d.tambem && d.tambem.length ? " cruz" : "";
  return "<span class='mark" + cruz + "' style='background:" + bg + "'>" + esc(label.slice(0, 2)) + "</span>";
}

function htmlPessoas(lista) {
  const q = busca.trim().toLocaleLowerCase("pt-BR");
  let rows = lista;
  if (q) rows = lista.filter(p => p.nome.toLocaleLowerCase("pt-BR").includes(q));
  return "<div class='pessoas'>" + rows.map(p =>
    "<div class='prow'><span>" + esc(p.nome) + "</span><b>" + brl(p.v) + "</b></div>"
  ).join("")
    + (rows.length === 0 ? "<p class='empty'>Nenhuma pessoa com esse nome nessa vaquinha.</p>" : "")
    + "</div>";
}

function casa(d, q) {
  if (!q) return true;
  const blob = (d.nome + " " + (d.tag || "") + " " + (d.tambem || []).join(" ")
    + " " + ((d.campanhas || []).map(k => k.urna + " " + (k.tag || "")).join(" "))
    + ((d.tambem && d.tambem.length) || d.campanhas ? " cruzado" : "")).toLocaleLowerCase("pt-BR");
  return blob.includes(q);
}
function redesenha() {
  const y = window.scrollY;
  drawDetail();
  window.scrollTo(0, y);
}
function bindTools(box) {
  const fecharBtn = box.querySelector("#fechar");
  if (fecharBtn) fecharBtn.addEventListener("click", fechar);
  const find = box.querySelector("#find");
  if (find) find.addEventListener("input", () => {
    busca = find.value;
    const pos = find.selectionStart;
    redesenha();
    const again = document.getElementById("find");
    if (again) { again.focus(); again.selectionStart = again.selectionEnd = pos; }
  });
  const so = box.querySelector("#soCruz");
  if (so) so.addEventListener("click", () => {
    soCruzados = !soCruzados;
    redesenha();
  });
  const tres = box.querySelector("#so3");
  if (tres) tres.addEventListener("click", () => {
    so3 = !so3;
    redesenha();
  });
  box.querySelectorAll("[data-ord]").forEach(b => {
    b.addEventListener("click", () => { ordem = b.dataset.ord; redesenha(); });
  });
  box.querySelectorAll("[data-tipo]").forEach(b => {
    b.addEventListener("click", () => {
      tipo = tipo === b.dataset.tipo ? "" : b.dataset.tipo;
      redesenha();
    });
  });
  box.querySelectorAll("[data-partido]").forEach(b => {
    b.addEventListener("click", () => {
      const p = b.dataset.partido;
      if (partidosSel.has(p)) partidosSel.delete(p);
      else partidosSel.add(p);
      redesenha();
    });
  });
  box.querySelectorAll(".camp").forEach(b => {
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      openCand(b.dataset.sq, true, b.dataset.q);
    });
  });
  box.querySelectorAll(".row.cruz").forEach(row => {
    const abrir = () => {
      const k = row.dataset.mov || "";
      if (!k) return;
      movAberto = movAberto === k ? "" : k;
      const y = window.scrollY;
      drawDetail();
      window.scrollTo(0, y);
    };
    row.addEventListener("click", (e) => {
      if (e.target.closest(".camp")) return;
      const y = window.scrollY;
      abrir();
      window.scrollTo(0, y);
    });
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        abrir();
      }
    });
  });
}
function dataBr(iso) {
  if (!iso || iso.length < 10) return "sem data";
  return iso.slice(8, 10) + "/" + iso.slice(5, 7) + "/" + iso.slice(0, 4);
}
function htmlMovs(d) {
  if (!d.movs || !d.movs.length || movAberto !== d.nome) return "";
  return "<div class='movs'>" + d.movs.map(m => {
    const pc = porUrna[m.urna];
    const dot = pc ? "<i class='pdot' style='background:" + pc.cor + "'></i>" : "";
    return "<div class='mrow'><span class='mdt'>" + esc(dataBr(m.dt)) + "</span>"
      + "<span class='murna'>" + dot + esc(m.urna) + "</span>"
      + "<span class='mcomo'>" + esc(m.como || "") + (m.n > 1 ? " · " + m.n + " aportes" : "") + "</span>"
      + "<b title='" + esc(brlCheio(m.v)) + "'>" + (m.v > 0 && m.v < 1 ? brlCheio(m.v) : brl(m.v)) + "</b></div>";
  }).join("") + "</div>";
}
function linhaDoador(d, i, total, cor, extraTag) {
  const pct = total ? d.v / total * 100 : 0;
  const cruzado = (d.tambem && d.tambem.length) || d.campanhas;
  const cruz = cruzado ? " cruz" : "";
  const tag = extraTag != null ? extraTag : htmlTag(d);
  const pill = cruzado ? "<span class='catpill'>cruzado</span>" : "";
  const temMov = d.movs && d.movs.length;
  return "<div class='block'><div class='row" + (i === 0 ? " top" : "") + cruz + "'"
    + (temMov ? " data-mov='" + esc(d.nome) + "' tabindex='0'" : "") + ">"
    + "<div class='rk'>" + (i + 1) + "</div>"
    + (d.campanhas
      ? "<span class='mark cruz' style='background:#2150e8'>" + d.n + "</span>"
      : marca(d, cor))
    + "<div class='id'><div class='nm'>" + esc(d.nome) + "</div>"
    + (tag || pill ? "<div class='tag'>" + pill + tag + "</div>" : "")
    + "</div>"
    + "<div class='share'><span class='pct'>" + pctLabel(pct) + "</span>"
    + "<span class='track'><i style='width:" + Math.min(100, pct).toFixed(2) + "%;background:" + cor + "'></i></span>"
    + "</div>"
    + "<div class='amt' title='" + esc(brlCheio(d.v)) + "'>" + (d.v > 0 && d.v < 1 ? brlCheio(d.v) : brl(d.v)) + "</div></div>"
    + htmlMovs(d) + "</div>";
}
function nCamps(d) {
  if (d.campanhas) return d.n || d.campanhas.length;
  return 1 + ((d.tambem && d.tambem.length) || 0);
}
function ultima(d) {
  if (d.dt) return d.dt;
  let best = "";
  (d.movs || []).forEach(m => { if (m.dt && m.dt > best) best = m.dt; });
  return best;
}
function tiposDe(d) {
  const t = (d.tag || "").toLocaleLowerCase("pt-BR");
  const set = new Set();
  if (t.indexOf("dinheiro público") >= 0) set.add("publico");
  if (t.indexOf("estimado") >= 0) set.add("estimado");
  if (t.indexOf("vaquinha") >= 0) set.add("vaquinha");
  if (t.indexOf("próprio") >= 0) set.add("proprio");
  if (t.indexOf("sem doador") >= 0 || t.indexOf("outro candidato") >= 0) set.add("partido");
  const semPessoa = t === "vaquinha" || t.indexOf("sem nome") >= 0 || set.has("publico") || set.has("estimado") || set.has("partido");
  if (!semPessoa) set.add("pessoa");
  if (!set.size) set.add("pessoa");
  return set;
}
function passa(d, q) {
  if (soCruzados && !(d.tambem && d.tambem.length) && !d.campanhas) return false;
  if (so3 && nCamps(d) < 3) return false;
  if (tipo && !tiposDe(d).has(tipo)) return false;
  if (partidosSel.size) {
    const urnas = d.campanhas ? d.campanhas.map(k => k.urna) : (d.tambem || []);
    let ok = false;
    urnas.forEach(u => {
      const c = porUrna[u];
      if (c && partidosSel.has(c.partido)) ok = true;
    });
    if (!ok) return false;
  }
  return casa(d, q);
}
function ordenar(lista) {
  const arr = lista.slice();
  if (ordem === "nome") arr.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR") || b.v - a.v);
  else if (ordem === "data") arr.sort((a, b) => {
    const da = ultima(a) || "0000", db = ultima(b) || "0000";
    if (da !== db) return da < db ? 1 : -1;
    return b.v - a.v;
  });
  else if (ordem === "camps") arr.sort((a, b) => nCamps(b) - nCamps(a) || b.v - a.v);
  else arr.sort((a, b) => b.v - a.v || a.nome.localeCompare(b.nome, "pt-BR"));
  return arr;
}
function contraste(hex) {
  const n = parseInt(String(hex || "").replace("#", ""), 16);
  if (!n && n !== 0) return "#fff";
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const L = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return L > 0.5 ? "#1c1c1c" : "#fff";
}
function htmlTag(d) {
  const bits = [];
  if (d.tambem && d.tambem.length) {
    const partes = d.tambem.map(u => {
      const c = porUrna[u];
      const dot = c ? "<i class='pdot' style='background:" + c.cor + "'></i>" : "";
      return dot + esc(u);
    });
    bits.push(partes.length === 1 ? "também em " + partes[0] : "também em " + partes.slice(0, -1).join(", ") + " e " + partes[partes.length - 1]);
  }
  if (d.tag) bits.push(esc(d.tag));
  if (d.n && !d.campanhas) bits.push(Number(d.n).toLocaleString("pt-BR") + " pessoas");
  return bits.join(" · ");
}
function htmlSort() {
  const opcoes = [["valor", "Valor"], ["nome", "Nome"], ["data", "Data"], ["camps", "Campanhas"]];
  return "<div class='sort' role='group' aria-label='Ordenar'>" + opcoes.map(o =>
    "<button type='button' data-ord='" + o[0] + "'" + (ordem === o[0] ? " class='on'" : "") + ">" + o[1] + "</button>"
  ).join("") + "</div>";
}
function htmlTipos(lista) {
  const counts = {};
  const rotulo = { pessoa: "Pessoa", vaquinha: "Vaquinha", publico: "Público", estimado: "Estimado", proprio: "Próprio bolso", partido: "Repasse" };
  lista.forEach(d => tiposDe(d).forEach(t => { counts[t] = (counts[t] || 0) + 1; }));
  return ["pessoa", "vaquinha", "publico", "estimado", "proprio", "partido"].filter(t => counts[t]).map(t =>
    "<button type='button' class='x filtro" + (tipo === t ? " on" : "") + "' data-tipo='" + t + "' aria-pressed='" + (tipo === t ? "true" : "false") + "'>"
    + rotulo[t] + " · " + counts[t].toLocaleString("pt-BR") + "</button>"
  ).join("");
}
function htmlPartidos(lista, excluir) {
  const counts = {};
  lista.forEach(d => {
    const urnas = d.campanhas ? d.campanhas.map(k => k.urna) : (d.tambem || []);
    const vistos = {};
    urnas.forEach(u => {
      const c = porUrna[u];
      if (!c || c.partido === excluir || vistos[c.partido]) return;
      vistos[c.partido] = 1;
      counts[c.partido] = (counts[c.partido] || 0) + 1;
    });
  });
  return Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b, "pt-BR")).map(p => {
    const cor = (porPartido[p] && porPartido[p].cor) || "#909EB1";
    const on = partidosSel.has(p);
    const ink = on ? contraste(cor) : "var(--text)";
    return "<button type='button' class='x part" + (on ? " on" : "") + "' data-partido='" + esc(p) + "' aria-pressed='" + (on ? "true" : "false") + "' style='background:" + (on ? cor : "#fff") + ";color:" + ink + ";border-color:" + cor + "'>"
      + "<i class='pdot' style='background:" + (on ? ink : cor) + "'></i>" + esc(p) + " · " + counts[p].toLocaleString("pt-BR") + "</button>";
  }).join("");
}
function htmlFiltros(lista, excluir, comCruz) {
  const nCruz = lista.filter(d => (d.tambem && d.tambem.length) || d.campanhas).length;
  const n3 = lista.filter(d => nCamps(d) >= 3).length;
  const cruzBtn = comCruz && nCruz
    ? "<button type='button' class='x filtro" + (soCruzados ? " on" : "") + "' id='soCruz' aria-pressed='" + (soCruzados ? "true" : "false") + "'>Mais de uma campanha · " + nCruz.toLocaleString("pt-BR") + "</button>"
    : "";
  const tresBtn = n3
    ? "<button type='button' class='x filtro" + (so3 ? " on" : "") + "' id='so3' aria-pressed='" + (so3 ? "true" : "false") + "'>3 ou mais · " + n3.toLocaleString("pt-BR") + "</button>"
    : "";
  return "<div class='filters'><span class='flab'>Ordenar</span>" + htmlSort()
    + "<span class='flab'>Filtrar</span>" + htmlTipos(lista) + cruzBtn + tresBtn + htmlPartidos(lista, excluir) + "</div>";
}
function htmlResumo(n, total) {
  if (n === total) return "";
  return "<p class='fmeta'>" + n.toLocaleString("pt-BR") + " de " + total.toLocaleString("pt-BR") + " · a barra continua sendo a parte do total</p>";
}
function drawCruzados() {
  const box = document.getElementById("detail");
  box.hidden = false;
  const q = busca.trim().toLocaleLowerCase("pt-BR");
  const base = DATA.cruzados || [];
  const lista = ordenar(base.filter(d => passa(d, q)));
  const total = DATA.cruzadosTotal || 0;
  const top6 = (DATA.cruzados || []).slice(0, 6).reduce((a, d) => a + d.v, 0);
  const pct6 = total ? top6 / total * 100 : 0;
  const fatia = (pct6 >= 99.5 && pct6 < 100)
    ? pct6.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
    : String(Math.round(pct6));
  const linhas = lista.map((d, i) => {
    const tag = d.campanhas.map(k => {
      const pc = porUrna[k.urna];
      const dot = pc ? "<i class='pdot' style='background:" + pc.cor + "'></i>" : "";
      return "<button type='button' class='camp' data-sq='" + esc(k.sq) + "' data-q='" + esc(k.nome || d.nome) + "'>"
        + dot + esc(k.urna) + " · " + (k.v > 0 && k.v < 1 ? brlCheio(k.v) : brl(k.v)) + (k.tag ? " · " + esc(k.tag) : "") + "</button>";
    }).join("<span class='sep'> · </span>");
    return linhaDoador(d, i, total, "#2150e8", tag);
  }).join("");
  const nota = base.length.toLocaleString("pt-BR")
    + " pessoas com o mesmo documento em duas ou mais campanhas desta eleição. "
    + (pct6 >= 80 ? "As seis maiores concentram " + fatia + "% do valor. " : "")
    + "A barra é a parte de cada uma nesse total. O dinheiro já está na campanha de cada um. O CPF não aparece.";
  box.innerHTML = "<header class='dhead'>"
    + "<span class='ini' style='background:#2150e8;border-color:#2150e8;font-family:JetBrains Mono,monospace'>2+</span>"
    + "<div><p class='kicker'>Categoria</p><h2>Doadores cruzados</h2>"
    + "<p class='civil'>A mesma pessoa em mais de uma campanha</p>"
    + "<p class='meta'>Eleição de 2026. O documento liga os nomes. O CPF não é publicado.</p></div>"
    + "<div class='metric'><p class='k'>Somado</p><p class='v' title='" + esc(brlCheio(total)) + "'>" + brl(total) + "</p></div></header>"
    + "<div class='tools'><p class='dnote'>" + nota + "</p>"
    + "<input class='find' id='find' placeholder='Buscar doador' value='" + esc(busca) + "'>"
    + "<button type='button' class='x' id='fechar'>Fechar</button></div>"
    + htmlFiltros(base, "", false)
    + htmlResumo(lista.length, base.length)
    + (linhas || "<p class='empty'>Nenhum doador com esses filtros.</p>");
  bindTools(box);
}
function drawDetail() {
  const box = document.getElementById("detail");
  if (aberto === "cruzados") { drawCruzados(); return; }
  const c = candBy(aberto);
  if (!c) { box.hidden = true; box.innerHTML = ""; return; }
  box.hidden = false;
  const q = busca.trim().toLocaleLowerCase("pt-BR");
  const base = c.doadores;
  const todos = ordenar(base.filter(d => passa(d, q)));
  const linhas = todos.map((d, i) => linhaDoador(d, i, c.total, c.cor)).join("");
  box.innerHTML = "<header class='dhead'>"
    + "<img alt='' style='border-color:" + c.cor + "' src='" + esc(c.foto) + "'>"
    + "<div><p class='kicker'>Quem declara</p><h2>" + esc(c.urna) + "</h2>"
    + "<p class='civil'>" + esc(c.nome) + "</p>"
    + "<p class='meta'>" + esc(c.partido) + " · nº " + esc(c.numero)
    + " · <a href='" + esc(c.url) + "' target='_blank' rel='noopener'>DivulgaCand</a></p></div>"
    + "<div class='metric'><p class='k'>Declarado</p><p class='v'>" + brl(c.total) + "</p></div></header>"
    + "<div class='tools'><p class='dnote'>Cada linha é um doador. Quem deu pela vaquinha aparece com o próprio nome. Fundo Especial e Fundo Partidário são dinheiro público. O aro azul doou a mais de uma campanha. Clique para ver valor e data.</p>"
    + "<input class='find' id='find' placeholder='Buscar doador' value='" + esc(busca) + "'>"
    + "<button type='button' class='x' id='fechar'>Fechar</button></div>"
    + htmlFiltros(base, c.partido, true)
    + htmlResumo(todos.length, base.length)
    + (linhas || "<p class='empty'>Nenhum doador com esses filtros.</p>");
  const img = box.querySelector(".dhead img");
  if (img) img.addEventListener("error", () => {
    const s = document.createElement("span");
    s.className = "ini";
    s.style.background = c.cor;
    s.style.borderColor = c.cor;
    s.textContent = iniciais(c.urna);
    img.replaceWith(s);
  });
  bindTools(box);
}

function openCand(sq, scroll, q) {
  aberto = sq;
  busca = q || "";
  soCruzados = false;
  so3 = false;
  ordem = "valor";
  tipo = "";
  partidosSel = new Set();
  movAberto = "";
  tip.hidden = true;
  renderCands();
  drawDetail();
  history.replaceState(null, "", "#" + sq);
  if (scroll) document.getElementById("detail").scrollIntoView({ behavior: "smooth", block: "start" });
}
function fechar() {
  aberto = null;
  movAberto = "";
  renderCands();
  drawDetail();
  history.replaceState(null, "", location.href.split("#")[0]);
}

function keyRow() {
  const bits = [DATA.lula, DATA.flavio, DATA.demais].map(g => {
    const inner = "<i class='sw' style='background:" + g.cor + "'></i>" + g.rotulo + " <b>" + brl(g.total) + "</b>";
    if (g.sq) return "<button type='button' class='keybtn' data-sq='" + g.sq + "'>" + inner + "</button>";
    return "<span>" + inner + "</span>";
  });
  const key = document.getElementById("key");
  key.innerHTML = bits.join("");
  key.querySelectorAll("button").forEach(b => b.addEventListener("click", () => openCand(b.dataset.sq, true)));
}

function layout() {
  draw("lula", DATA.lula);
  draw("flavio", DATA.flavio);
  draw("demais", DATA.demais);
}
keyRow();
renderCands();
document.getElementById("lula").addEventListener("click", () => openCand(DATA.lula.sq, true));
document.getElementById("flavio").addEventListener("click", () => openCand(DATA.flavio.sq, true));
document.getElementById("fonte").innerHTML =
  "Fonte · TSE, prestação de contas eleitorais de candidatos 2026, arquivo gerado em " + DATA.gerado + " às " + DATA.hora +
  ". Presidente, Brasil. Receitas idênticas contam uma vez. Do lado de Lula, tudo o que não é o diretório nacional fica num único retângulo. Do lado de Flávio, doador com menos de R$ 500 mil entra em Outros doadores. Nas demais candidaturas, o corte é R$ 200 mil. " +
  "No detalhe, o doador originário abre o repasse do partido e a vaquinha. " +
  "A categoria Cruzados reúne a mesma pessoa em duas ou mais campanhas desta eleição, ligada pelo documento. O CPF não aparece. Filtrar e ordenar não altera o valor. " +
  "Contas parciais, prestação final do 1º turno aberta até 3 de novembro. " +
  "<a href='https://dadosabertos.tse.jus.br/dataset/prestacao-de-contas-eleitorais-2026'>Dados abertos do TSE</a>.";
layout();
window.addEventListener("resize", layout);
const hash = location.hash.replace("#", "");
if (hash === "cruzados" || candBy(hash)) openCand(hash, false);
</script>
</body>
</html>
"""
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
text = html.replace("__DATA__", payload)
for dest in (ROOT / "index.html", ROOT / "doadores-presidencial-2026.html"):
    dest.write_text(text, encoding="utf-8")
    print("wrote", dest, dest.stat().st_size)
loose = Path("/Users/diazaraujo/Desktop/doadores-presidencial-2026.html")
if loose.parent.is_dir() and loose.resolve() != (ROOT / "doadores-presidencial-2026.html").resolve():
    loose.write_text(text, encoding="utf-8")
    print("wrote", loose, loose.stat().st_size)
