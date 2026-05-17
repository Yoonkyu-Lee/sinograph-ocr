"""canonical_v3 completion — step 5: app-facing query layer.

Adds two things the dictionary app needs that the normalized tables do not
give directly:

  character_summary  — a VIEW joining core + structure + ids, so one
                       character is a single-row fetch instead of a 3-table
                       join in the app code.
  fts_search         — an FTS5 virtual table for reverse lookup: find a
                       character by typing a meaning, reading, or 자훈.
                       One row per character, columns reading / hunum /
                       meaning, unicode61 tokenizer.

Run (after 60 / 61 / 62 / 65):
  python sinograph_canonical_v3/scripts/66_build_app_layer.py
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DST_DB = Path(__file__).resolve().parents[1] / "out" / "canonical_v3.sqlite"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[66] run 60-65 first — not found: {DST_DB}")
    db = sqlite3.connect(DST_DB)

    # --- character_summary VIEW ---
    log("[66] creating character_summary VIEW ...")
    db.execute("DROP VIEW IF EXISTS character_summary")
    db.execute(
        "CREATE VIEW character_summary AS "
        "SELECT c.codepoint, c.character, c.block, "
        "s.radical_idx, s.total_strokes, s.residual_strokes, "
        "i.primary_ids, i.ids_top_idc "
        "FROM characters_core c "
        "LEFT JOIN characters_structure s ON c.codepoint = s.codepoint "
        "LEFT JOIN characters_ids i ON c.codepoint = i.codepoint")
    vn = db.execute("SELECT count(*) FROM character_summary").fetchone()[0]
    log(f"[66]   character_summary: {vn:,} rows")

    # --- fts_search FTS5 table ---
    log("[66] aggregating searchable text ...")
    readings: dict[str, list[str]] = defaultdict(list)
    for cp, val in db.execute(
            "SELECT codepoint, value FROM character_readings"):
        readings[cp].append(val)
    hunum: dict[str, list[str]] = defaultdict(list)
    for cp, jahun, dokeum in db.execute(
            "SELECT codepoint, jahun, dokeum FROM character_hunum"):
        if jahun:
            hunum[cp].append(jahun)
        if dokeum:
            hunum[cp].append(dokeum)
    meanings: dict[str, list[str]] = defaultdict(list)
    for cp, val in db.execute(
            "SELECT codepoint, value FROM character_meanings"):
        meanings[cp].append(val)
    chars = dict(db.execute("SELECT codepoint, character FROM characters_core"))

    all_cps = sorted(set(readings) | set(hunum) | set(meanings))
    rows = [(cp, chars.get(cp, ""),
             " ".join(readings.get(cp, [])),
             " ".join(hunum.get(cp, [])),
             " ".join(meanings.get(cp, [])))
            for cp in all_cps]

    log("[66] building fts_search (FTS5, unicode61) ...")
    db.execute("DROP TABLE IF EXISTS fts_search")
    db.execute(
        "CREATE VIRTUAL TABLE fts_search USING fts5("
        "codepoint UNINDEXED, hanja UNINDEXED, "
        "reading, hunum, meaning, tokenize='unicode61')")
    db.executemany(
        "INSERT INTO fts_search VALUES (?,?,?,?,?)", rows)
    db.commit()
    log(f"[66]   fts_search: {len(rows):,} rows")

    # smoke queries
    for q in ("거울", "mirror", "jiàn"):
        hits = db.execute(
            "SELECT count(*) FROM fts_search WHERE fts_search MATCH ?",
            (f'"{q}"',)).fetchone()[0]
        log(f"[66]   MATCH '{q}': {hits:,} hits")

    db.close()
    size_mb = DST_DB.stat().st_size / (1024 * 1024)
    log(f"[66] done: {DST_DB.name}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
