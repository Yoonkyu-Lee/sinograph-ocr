"""canonical_v3 completion — step 3: merge Korean 훈음 (자훈 + 독음).

canonical_v2 carried only the Korean reading syllable (독음). It dropped the
자훈 — the native-Korean gloss word that pairs with it. e-hanja online keeps
both in `tree.jsonl` getHunum.

getHunum[].hRead format: `"기운 뻗칠 하, 꾸짖을 가"` — comma-separated 훈음
entries, each `"<자훈 ...> <독음>"`. The last whitespace token is the 독음,
the rest is the 자훈.

For every codepoint with a usable getHunum, this script:
  - replaces v2's unpaired `dokeum` rows with the getHunum-derived pair,
  - adds `jahun` rows,
  - ties 자훈 <-> 독음 with a shared `pair_group` (0, 1, ...).
Codepoints without getHunum keep v2's `dokeum` rows untouched.

Run (after 61_migrate_lexical_from_v2.py):
  python sinograph_canonical_v3/scripts/62_merge_hunum.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DST_DB = ROOT / "sinograph_canonical_v3" / "out" / "canonical_v3.sqlite"
TREE_JSONL = ROOT / "db_src" / "e-hanja_online" / "tree.jsonl"


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_hread(hread: str) -> list[tuple[str, str]]:
    """`"기운 뻗칠 하, 꾸짖을 가"` -> [("기운 뻗칠","하"), ("꾸짖을","가")].

    A 훈음 with no internal space yields ("", 독음).
    """
    pairs = []
    for chunk in hread.split(","):
        chunk = chunk.strip()
        if not chunk or chunk == "-":
            continue
        if " " in chunk:
            jahun, dokeum = chunk.rsplit(" ", 1)
            pairs.append((jahun.strip(), dokeum.strip()))
        else:
            pairs.append(("", chunk))
    return pairs


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[62] run 60/61 first — not found: {DST_DB}")
    if not TREE_JSONL.exists():
        raise SystemExit(f"[62] not found: {TREE_JSONL}")

    dst = sqlite3.connect(DST_DB)
    universe = {r[0] for r in dst.execute("SELECT codepoint FROM characters_ids")}
    log(f"[62] v3 universe: {len(universe):,} codepoints")

    # cp -> ordered, de-duplicated list of (jahun, dokeum) pairs
    log(f"[62] parsing getHunum from {TREE_JSONL.name} ...")
    hunum: dict[str, list[tuple[str, str]]] = {}
    scanned = 0
    with open(TREE_JSONL, encoding="utf-8") as f:
        for line in f:
            scanned += 1
            d = json.loads(line)
            ch = d.get("char")
            if not ch:
                continue
            cp = f"U+{ord(ch[0]):04X}"
            if cp not in universe:
                continue
            seen, pairs = set(), []
            for entry in d.get("getHunum") or []:
                for pair in parse_hread(entry.get("hRead", "") or ""):
                    if pair not in seen:
                        seen.add(pair)
                        pairs.append(pair)
            if pairs:
                hunum[cp] = pairs
    total_pairs = sum(len(v) for v in hunum.values())
    log(f"[62]   scanned {scanned:,} tree rows")
    log(f"[62]   codepoints with usable 훈음: {len(hunum):,}")
    log(f"[62]   total 훈음 pairs: {total_pairs:,}")

    # Replace the Korean hunum slice for these codepoints. Both jahun and
    # dokeum are deleted (not just dokeum) so a rerun is idempotent — the
    # previous run's jahun rows are cleared before re-insertion. Codepoints
    # with no getHunum keep v2's unpaired dokeum untouched.
    log("[62] replacing jahun + dokeum for hunum codepoints ...")
    dst.executemany(
        "DELETE FROM character_readings "
        "WHERE reading_type IN ('jahun', 'dokeum') AND codepoint=?",
        [(cp,) for cp in hunum])

    new_rows = []
    for cp, pairs in hunum.items():
        for grp, (jahun, dokeum) in enumerate(pairs):
            if jahun:
                new_rows.append((cp, "jahun", jahun, grp))
            if dokeum:
                new_rows.append((cp, "dokeum", dokeum, grp))
    dst.executemany("INSERT INTO character_readings VALUES (?,?,?,?)", new_rows)

    dst.commit()

    jahun_cp = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_readings "
        "WHERE reading_type='jahun'").fetchone()[0]
    dokeum_cp = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_readings "
        "WHERE reading_type='dokeum'").fetchone()[0]
    dokeum_paired = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_readings "
        "WHERE reading_type='dokeum' AND pair_group IS NOT NULL").fetchone()[0]
    log(f"[62]   inserted {len(new_rows):,} rows")
    log(f"[62]   jahun  : {jahun_cp:,} codepoints")
    log(f"[62]   dokeum : {dokeum_cp:,} codepoints "
        f"({dokeum_paired:,} now paired with 자훈, rest from v2)")

    dst.close()
    log(f"[62] done: {DST_DB.name}")


if __name__ == "__main__":
    main()
