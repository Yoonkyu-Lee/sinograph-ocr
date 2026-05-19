"""canonical_v3 completion — step: build the character_grades table.

급수 — per-character grade / level across four standard sets, so the app
can show how mainstream a character is:

  kr_grade     — 한국 한자검정 (한국어문회) 급수        e-hanja online
  kr_education — 한문 교육용 기초한자 (중학용 / 고등용)  e-hanja online
  cn_tonggyong — 중국 통용규범한자표 등급 1 / 2 / 3      TONGYONG_GUIFAN
  jp_grade     — 일본 학년별 배당 (1-8 상용 / 9-10 인명) KANJIDIC2
  jp_freq      — 일본 신문 빈도 순위 (1 = 최빈)          KANJIDIC2
  jp_jlpt      — 옛 JLPT 급 (1-4)                        KANJIDIC2
  unihan_core  — kUnihanCore2020 지역 태그 (G/H/J/K/…)   Unihan

One row per codepoint that has at least one of these. Idempotent.

Run (after 60 / 61 / 62 / 67):
  python sinograph_canonical_v3/scripts/68_build_grades.py
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DST_DB = ROOT / "sinograph_canonical_v3" / "out" / "canonical_v3.sqlite"
DB_SRC = ROOT / "db_src"
EHANJA_DETAIL = DB_SRC / "e-hanja_online" / "detail.jsonl"
TONGYONG_CSV = DB_SRC / "TONGYONG_GUIFAN" / "tongyong_guifan_2013.csv"
KANJIDIC2_XML = DB_SRC / "KANJIDIC2" / "KANJIDIC2_xml" / "kanjidic2.xml"
UNIHAN_DICT = DB_SRC / "Unihan" / "Unihan_txt" / "Unihan_DictionaryLikeData.txt"

TONGYONG_LEVEL = {"一级字表": 1, "二级字表": 2, "三级字表": 3}

FIELDS = ("kr_grade", "kr_education", "cn_tonggyong",
          "jp_grade", "jp_freq", "jp_jlpt", "unihan_core")


def log(msg: str) -> None:
    print(msg, flush=True)


def char_to_cp(ch: str) -> str | None:
    """NFKC-normalized first character -> U+XXXX (compat forms folded)."""
    if not ch:
        return None
    norm = unicodedata.normalize("NFKC", ch)
    if not norm:
        return None
    return f"U+{ord(norm[0]):04X}"


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[68] run 60-67 first — not found: {DST_DB}")
    for p in (EHANJA_DETAIL, TONGYONG_CSV, KANJIDIC2_XML, UNIHAN_DICT):
        if not p.exists():
            raise SystemExit(f"[68] not found: {p}")

    dst = sqlite3.connect(DST_DB)
    universe = {r[0] for r in dst.execute("SELECT codepoint FROM characters_ids")}
    log(f"[68] v3 universe: {len(universe):,} codepoints")

    grades: dict[str, dict] = {}

    def put(cp: str, field: str, value) -> None:
        if cp in universe and value is not None:
            grades.setdefault(cp, {})[field] = value

    # 1. e-hanja — 한자검정 급수 + 교육용
    kr_g = kr_e = 0
    with open(EHANJA_DETAIL, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            cp = char_to_cp(d.get("char") or "")
            cl = d.get("classification") or {}
            if not cp:
                continue
            raw = (cl.get("hanja_grade") or "").strip()
            if raw and raw not in ("-", "- (-)"):
                grade = raw.split("(")[0].strip()
                if grade and grade != "-":
                    put(cp, "kr_grade", grade)
                    kr_g += 1
            edu = (cl.get("education_level") or "").strip()
            if edu and edu != "-":
                put(cp, "kr_education", edu)
                kr_e += 1
    log(f"[68] e-hanja: 한자검정 {kr_g:,} · 교육용 {kr_e:,}")

    # 2. TONGYONG GUIFAN — 통용규범 등급
    cn = 0
    with open(TONGYONG_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cp = char_to_cp(row.get("character") or "")
            level = TONGYONG_LEVEL.get((row.get("bucket") or "").strip())
            if cp and level:
                put(cp, "cn_tonggyong", level)
                cn += 1
    log(f"[68] TONGYONG 통용규범: {cn:,}")

    # 3. KANJIDIC2 — grade / freq / jlpt
    jg = jf = jj = 0
    for ch in ET.parse(KANJIDIC2_XML).getroot().findall("character"):
        lit = ch.findtext("literal")
        misc = ch.find("misc")
        cp = char_to_cp(lit or "")
        if not cp or misc is None:
            continue
        for tag, field in (("grade", "jp_grade"), ("freq", "jp_freq"),
                            ("jlpt", "jp_jlpt")):
            text = misc.findtext(tag)
            if text and text.strip().isdigit():
                put(cp, field, int(text))
        if "jp_grade" in grades.get(cp, {}):
            jg += 1
        if "jp_freq" in grades.get(cp, {}):
            jf += 1
        if "jp_jlpt" in grades.get(cp, {}):
            jj += 1
    log(f"[68] KANJIDIC2: grade {jg:,} · freq {jf:,} · jlpt {jj:,}")

    # 4. Unihan kUnihanCore2020 — 지역 태그
    uc = 0
    with open(UNIHAN_DICT, encoding="utf-8") as f:
        for line in f:
            if "\tkUnihanCore2020\t" not in line:
                continue
            cp, _field, value = line.rstrip("\n").split("\t", 2)
            put(cp, "unihan_core", value.strip())
            if cp in universe:
                uc += 1
    log(f"[68] Unihan kUnihanCore2020: {uc:,}")

    # build table
    log("[68] building character_grades ...")
    dst.execute("DROP TABLE IF EXISTS main.character_grades")
    dst.execute(
        "CREATE TABLE character_grades ("
        "codepoint TEXT PRIMARY KEY, kr_grade TEXT, kr_education TEXT, "
        "cn_tonggyong INTEGER, jp_grade INTEGER, jp_freq INTEGER, "
        "jp_jlpt INTEGER, unihan_core TEXT)")
    rows = [
        (cp, *(g.get(f) for f in FIELDS))
        for cp, g in sorted(grades.items())
    ]
    dst.executemany(
        "INSERT INTO character_grades VALUES (?,?,?,?,?,?,?,?)", rows)
    dst.execute("CREATE INDEX idx_grades_cp ON character_grades(codepoint)")
    dst.commit()

    n = len(universe)
    log(f"[68]   character_grades: {len(rows):,} codepoints "
        f"({100*len(rows)/n:.2f}% of universe)")
    for f in FIELDS:
        cnt = dst.execute(
            f"SELECT count(*) FROM character_grades WHERE {f} IS NOT NULL"
        ).fetchone()[0]
        log(f"[68]     {f:<13s}: {cnt:,}")
    dst.close()
    log(f"[68] done: {DST_DB.name}")


if __name__ == "__main__":
    main()
