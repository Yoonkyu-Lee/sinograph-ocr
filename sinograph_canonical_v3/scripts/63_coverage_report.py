"""canonical_v3 completion — step 4: coverage report.

Recomputes per-field coverage over the completed `canonical_v3.sqlite` and
writes `out/canonical_v3_coverage.json` plus a stdout table. This is the
ground-truth "정보 없음 / 빈 비율" readout for doc/36.

Run (after 60 / 61 / 62):
  python sinograph_canonical_v3/scripts/63_coverage_report.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).resolve().parents[1] / "out"
DST_DB = OUT_DIR / "canonical_v3.sqlite"
OUT_JSON = OUT_DIR / "canonical_v3_coverage.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[63] run 60/61/62 first — not found: {DST_DB}")
    db = sqlite3.connect(DST_DB)

    n = db.execute("SELECT count(*) FROM characters_ids").fetchone()[0]

    def cp_count(sql: str, params: tuple = ()) -> int:
        return db.execute(sql, params).fetchone()[0]

    # group label -> (count of codepoints having the field)
    groups: list[tuple[str, list[tuple[str, int]]]] = [
        ("구조 (structure)", [
            ("radical_idx", cp_count(
                "SELECT count(*) FROM characters_structure "
                "WHERE radical_idx IS NOT NULL")),
            ("total_strokes", cp_count(
                "SELECT count(*) FROM characters_structure "
                "WHERE total_strokes IS NOT NULL")),
            ("residual_strokes", cp_count(
                "SELECT count(*) FROM characters_structure "
                "WHERE residual_strokes IS NOT NULL")),
            ("ids_decomposition", cp_count(
                "SELECT count(*) FROM characters_ids "
                "WHERE primary_ids IS NOT NULL AND primary_ids<>''")),
        ]),
        ("발음 (readings)", [
            ("any reading", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings")),
            ("mandarin", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='mandarin'")),
            ("cantonese", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='cantonese'")),
            ("onyomi (일본 음독)", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='onyomi'")),
            ("kunyomi (일본 훈독)", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='kunyomi'")),
            ("vietnamese", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='vietnamese'")),
            ("dokeum (한국 독음)", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='dokeum'")),
            ("jahun (한국 자훈)", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_readings "
                "WHERE reading_type='jahun'")),
        ]),
        ("뜻 (meanings)", [
            ("any meaning", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_meanings")),
            ("meaning ko", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_meanings "
                "WHERE language='ko'")),
            ("meaning en", cp_count(
                "SELECT count(DISTINCT codepoint) FROM character_meanings "
                "WHERE language='en'")),
        ]),
        ("이체자 (variants)", [
            ("variant edge (as source)", cp_count(
                "SELECT count(DISTINCT source_codepoint) FROM variant_edges")),
            ("family member 2+", cp_count(
                "SELECT count(*) FROM variant_family WHERE component_size>1")),
        ]),
    ]

    report = {"universe": n, "groups": {}}
    log("=" * 64)
    log(f"  canonical_v3 coverage  —  universe = {n:,} codepoints")
    log("=" * 64)
    for gname, fields in groups:
        log(f"\n  [{gname}]")
        report["groups"][gname] = {}
        for label, cnt in fields:
            pct = 100.0 * cnt / n
            empty = 100.0 - pct
            log(f"    {label:<26s} {cnt:>8,}  {pct:6.2f}%   (빈: {empty:5.2f}%)")
            report["groups"][gname][label] = {
                "count": cnt, "pct": round(pct, 2),
                "empty_pct": round(empty, 2)}

    # table row totals
    rd_rows = db.execute("SELECT count(*) FROM character_readings").fetchone()[0]
    mn_rows = db.execute("SELECT count(*) FROM character_meanings").fetchone()[0]
    ed_rows = db.execute("SELECT count(*) FROM variant_edges").fetchone()[0]
    fam_rows = db.execute("SELECT count(*) FROM variant_family").fetchone()[0]
    report["table_rows"] = {
        "characters_ids": n,
        "characters_structure": db.execute(
            "SELECT count(*) FROM characters_structure").fetchone()[0],
        "characters_core": db.execute(
            "SELECT count(*) FROM characters_core").fetchone()[0],
        "character_readings": rd_rows,
        "character_meanings": mn_rows,
        "variant_edges": ed_rows,
        "variant_family": fam_rows,
    }
    log("\n  [table row counts]")
    for t, c in report["table_rows"].items():
        log(f"    {t:<26s} {c:>8,}")

    db.close()
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    log(f"\n[63] written: {OUT_JSON}")


if __name__ == "__main__":
    main()
