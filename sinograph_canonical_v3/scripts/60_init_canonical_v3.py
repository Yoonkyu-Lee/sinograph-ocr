"""canonical_v3 completion — step 1: init the completed DB.

Copies the two structure tables from the build intermediate
(`out/ids_merged.sqlite`) into a fresh `out/canonical_v3.sqlite`, and
builds the `characters_core` master table (codepoint / character / block).

The lexical tables (readings, meanings, variant edges/family) are added by
the later 61 / 62 scripts. `ids_merged.sqlite` is read-only here.

Run:
  python sinograph_canonical_v3/scripts/60_init_canonical_v3.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).resolve().parents[1] / "out"
SRC_DB = OUT_DIR / "ids_merged.sqlite"
DST_DB = OUT_DIR / "canonical_v3.sqlite"

STRUCTURE_TABLES = ("characters_ids", "characters_structure")

# Unicode block ranges relevant to the Han universe. (start, end, name).
# Ordered; first containing range wins.
BLOCKS = [
    (0x2E80, 0x2EFF, "CJK Radicals Supplement"),
    (0x2F00, 0x2FDF, "Kangxi Radicals"),
    (0x3400, 0x4DBF, "CJK Ext A"),
    (0x4E00, 0x9FFF, "CJK Unified"),
    (0xF900, 0xFAFF, "CJK Compatibility Ideographs"),
    (0x20000, 0x2A6DF, "CJK Ext B"),
    (0x2A700, 0x2B73F, "CJK Ext C"),
    (0x2B740, 0x2B81F, "CJK Ext D"),
    (0x2B820, 0x2CEAF, "CJK Ext E"),
    (0x2CEB0, 0x2EBEF, "CJK Ext F"),
    (0x2EBF0, 0x2EE5F, "CJK Ext I"),
    (0x2F800, 0x2FA1F, "CJK Compatibility Ideographs Supplement"),
    (0x30000, 0x3134F, "CJK Ext G"),
    (0x31350, 0x323AF, "CJK Ext H"),
    (0x323B0, 0x3347F, "CJK Ext J"),
]


def log(msg: str) -> None:
    print(msg, flush=True)


def cp_to_int(cp: str) -> int:
    return int(cp[2:], 16)


def block_of(cp_int: int) -> str:
    for start, end, name in BLOCKS:
        if start <= cp_int <= end:
            return name
    return "(other)"


def copy_table(dst: sqlite3.Connection, src: sqlite3.Connection,
               name: str) -> int:
    """Recreate `name` (schema + rows) in `dst` from `src`.

    `src` is a separate read-only connection (not ATTACH-ed). Unqualified
    DDL therefore stays inside `dst` and cannot touch the source file.
    """
    create_sql = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    if not create_sql:
        raise SystemExit(f"[60] source table missing: {name}")
    dst.execute(f"DROP TABLE IF EXISTS main.{name}")
    dst.execute(create_sql[0])
    rows = src.execute(f"SELECT * FROM {name}").fetchall()
    ncols = len(rows[0]) if rows else len(
        src.execute(f"PRAGMA table_info({name})").fetchall())
    dst.executemany(
        f"INSERT INTO {name} VALUES ({','.join('?' * ncols)})", rows)
    return dst.execute(f"SELECT count(*) FROM {name}").fetchone()[0]


def main() -> None:
    if not SRC_DB.exists():
        raise SystemExit(f"[60] not found: {SRC_DB}")
    if DST_DB.exists():
        log(f"[60] removing stale {DST_DB.name}")
        DST_DB.unlink()

    log(f"[60] init {DST_DB.name} from {SRC_DB.name}")
    dst = sqlite3.connect(DST_DB)
    # read-only source connection — never ATTACH-ed, so no DDL can reach it.
    src = sqlite3.connect(f"file:{SRC_DB}?mode=ro", uri=True)

    for name in STRUCTURE_TABLES:
        n = copy_table(dst, src, name)
        log(f"[60]   copied {name}: {n:,} rows")

    # characters_core master — one row per codepoint in characters_ids.
    log("[60] building characters_core ...")
    dst.execute("DROP TABLE IF EXISTS characters_core")
    dst.execute(
        "CREATE TABLE characters_core ("
        "codepoint TEXT PRIMARY KEY, character TEXT, block TEXT)"
    )
    cps = [r[0] for r in dst.execute(
        "SELECT codepoint FROM characters_ids ORDER BY codepoint")]
    rows = []
    bad = 0
    for cp in cps:
        ci = cp_to_int(cp)
        try:
            ch = chr(ci)
        except (ValueError, OverflowError):
            ch = ""
            bad += 1
        rows.append((cp, ch, block_of(ci)))
    dst.executemany("INSERT INTO characters_core VALUES (?,?,?)", rows)
    log(f"[60]   characters_core: {len(rows):,} rows ({bad} without literal char)")

    # block distribution — quick sanity readout
    log("[60] block distribution:")
    for blk, cnt in dst.execute(
        "SELECT block, count(*) FROM characters_core "
        "GROUP BY block ORDER BY count(*) DESC"
    ):
        log(f"[60]   {blk:<42s} {cnt:>7,}")

    dst.commit()
    src.close()
    dst.close()

    size_mb = DST_DB.stat().st_size / (1024 * 1024)
    log(f"[60] done: {DST_DB}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
