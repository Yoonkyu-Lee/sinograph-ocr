"""canonical_v3 completion — step: rebuild Japanese readings in kana.

v2 carried Japanese readings from Unihan's legacy kJapaneseOn / kJapaneseKun
fields — uppercase romaji, only ~13k codepoints, multiple readings crammed
into one value. This script discards that and rebuilds `onyomi` / `kunyomi`
in kana from two kana-native sources:

  KANJIDIC2  ja_on (katakana) / ja_kun (hiragana)  — ~12k common kanji,
             one reading per element, keeps okurigana '.' notation.
  Unihan     kJapanese  — ~52k codepoints, on (katakana) + kun (hiragana)
             mixed in one space-separated field.

KANJIDIC2 takes priority (finer notation); Unihan kJapanese fills every
codepoint KANJIDIC2 does not cover. Coverage goes from ~13% to ~50%, and
every value is kana.

Idempotent: onyomi / kunyomi rows are deleted and rebuilt on every run.

Run (after 61_migrate_lexical_from_v2.py):
  python sinograph_canonical_v3/scripts/67_merge_japanese.py
"""
from __future__ import annotations

import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DST_DB = ROOT / "sinograph_canonical_v3" / "out" / "canonical_v3.sqlite"
KANJIDIC2_XML = ROOT / "db_src" / "KANJIDIC2" / "KANJIDIC2_xml" / "kanjidic2.xml"
UNIHAN_READINGS = ROOT / "db_src" / "Unihan" / "Unihan_txt" / "Unihan_Readings.txt"


def log(msg: str) -> None:
    print(msg, flush=True)


def has_hiragana(token: str) -> bool:
    """True if the token carries any hiragana (the prolonged mark ー, which
    sits in the katakana block but is script-neutral, does not count)."""
    return any(0x3040 <= ord(c) <= 0x309F for c in token)


def add(d: dict, cp: str, rt: str, value: str) -> None:
    value = value.strip()
    if not value:
        return
    bucket = d.setdefault(cp, {"onyomi": [], "kunyomi": []})[rt]
    if value not in bucket:
        bucket.append(value)


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[67] run 60/61 first — not found: {DST_DB}")
    for p in (KANJIDIC2_XML, UNIHAN_READINGS):
        if not p.exists():
            raise SystemExit(f"[67] not found: {p}")

    dst = sqlite3.connect(DST_DB)
    universe = {r[0] for r in dst.execute("SELECT codepoint FROM characters_ids")}
    log(f"[67] v3 universe: {len(universe):,} codepoints")

    # readings[cp] = {"onyomi": [...], "kunyomi": [...]}
    readings: dict[str, dict[str, list[str]]] = {}

    # 1. KANJIDIC2 — authoritative, finer notation
    log(f"[67] parsing {KANJIDIC2_XML.name} ...")
    kd_cps: set[str] = set()
    for ch in ET.parse(KANJIDIC2_XML).getroot().findall("character"):
        lit = ch.findtext("literal")
        if not lit:
            continue
        cp = f"U+{ord(lit[0]):04X}"
        if cp not in universe:
            continue
        got = False
        for r in ch.iter("reading"):
            t = r.get("r_type")
            if t == "ja_on" and r.text:
                add(readings, cp, "onyomi", r.text)
                got = True
            elif t == "ja_kun" and r.text:
                add(readings, cp, "kunyomi", r.text)
                got = True
        if got:
            kd_cps.add(cp)
    log(f"[67]   KANJIDIC2: {len(kd_cps):,} codepoints with kana readings")

    # 2. Unihan kJapanese — fills codepoints KANJIDIC2 does not cover
    log(f"[67] parsing kJapanese from {UNIHAN_READINGS.name} ...")
    uh_cps = 0
    with open(UNIHAN_READINGS, encoding="utf-8") as f:
        for line in f:
            if "\tkJapanese\t" not in line:
                continue
            cp, _field, value = line.rstrip("\n").split("\t", 2)
            if cp not in universe or cp in kd_cps:
                continue
            took = False
            for tok in value.split():
                rt = "kunyomi" if has_hiragana(tok) else "onyomi"
                add(readings, cp, rt, tok)
                took = True
            if took:
                uh_cps += 1
    log(f"[67]   Unihan kJapanese: {uh_cps:,} extra codepoints (not in KANJIDIC2)")

    # 3. rebuild onyomi / kunyomi rows
    log("[67] rebuilding onyomi / kunyomi in character_readings ...")
    dst.execute(
        "DELETE FROM character_readings "
        "WHERE reading_type IN ('onyomi', 'kunyomi')")
    rows = []
    for cp, bucket in readings.items():
        for rt in ("onyomi", "kunyomi"):
            for value in bucket[rt]:
                rows.append((cp, rt, value))
    dst.executemany("INSERT INTO character_readings VALUES (?,?,?)", rows)
    dst.commit()

    on_cp = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_readings "
        "WHERE reading_type='onyomi'").fetchone()[0]
    kun_cp = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_readings "
        "WHERE reading_type='kunyomi'").fetchone()[0]
    any_cp = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_readings "
        "WHERE reading_type IN ('onyomi','kunyomi')").fetchone()[0]
    n = len(universe)
    log(f"[67]   inserted {len(rows):,} rows")
    log(f"[67]   onyomi : {on_cp:,} codepoints ({100*on_cp/n:.2f}%)")
    log(f"[67]   kunyomi: {kun_cp:,} codepoints ({100*kun_cp/n:.2f}%)")
    log(f"[67]   any Japanese reading: {any_cp:,} ({100*any_cp/n:.2f}%)")

    dst.close()
    log(f"[67] done: {DST_DB.name}")


if __name__ == "__main__":
    main()
