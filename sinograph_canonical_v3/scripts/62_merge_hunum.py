"""canonical_v3 completion — step 3: build the character_hunum table.

Korean hanja readings are 자훈(訓: the native-Korean gloss, "거울") + 독음
(音: the Sino-Korean syllable, "감"). Unlike the other languages these two
form a pair, so they get their own table instead of being squeezed into
character_readings with a nullable pair_group.

`character_hunum(codepoint, seq, jahun, dokeum)`:
  - one row per 훈음 pair, `seq` ordering them (行 -> seq0 다닐/행, seq1 항렬/항)
  - `jahun` is nullable: codepoints with only a 독음 (no e-hanja getHunum)
    get a row with jahun = NULL
  - `dokeum` is always present

Sources:
  - e-hanja online tree.jsonl getHunum -> paired (자훈, 독음)
  - canonical_v2 korean_hangul -> 독음 for codepoints with no getHunum

Idempotent: the table is dropped and rebuilt on every run.

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
V2_DB = ROOT / "sinograph_canonical_v2" / "out" / "sinograph_canonical_v2.sqlite"
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
    for p in (V2_DB, TREE_JSONL):
        if not p.exists():
            raise SystemExit(f"[62] not found: {p}")

    dst = sqlite3.connect(DST_DB)
    v2 = sqlite3.connect(f"file:{V2_DB}?mode=ro", uri=True)
    universe = {r[0] for r in dst.execute("SELECT codepoint FROM characters_ids")}
    log(f"[62] v3 universe: {len(universe):,} codepoints")

    # 1. e-hanja getHunum -> ordered, de-duplicated (jahun, dokeum) pairs
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
    log(f"[62]   scanned {scanned:,} tree rows; "
        f"{len(hunum):,} codepoints with 훈음 pairs")

    # 2. v2 korean_hangul (독음) — used only for codepoints with no getHunum
    v2_dokeum: dict[str, list[str]] = {}
    for cp, val in v2.execute(
            "SELECT codepoint, value FROM character_readings "
            "WHERE reading_type='korean_hangul'"):
        if cp in universe and cp not in hunum:
            v2_dokeum.setdefault(cp, [])
            if val not in v2_dokeum[cp]:
                v2_dokeum[cp].append(val)
    log(f"[62]   {len(v2_dokeum):,} extra codepoints with 독음 only (no getHunum)")

    # 3. build the table
    log("[62] building character_hunum ...")
    dst.execute("DROP TABLE IF EXISTS main.character_hunum")
    dst.execute(
        "CREATE TABLE character_hunum ("
        "codepoint TEXT, seq INTEGER, jahun TEXT, dokeum TEXT)")
    rows = []
    for cp, pairs in hunum.items():
        for seq, (jahun, dokeum) in enumerate(pairs):
            rows.append((cp, seq, jahun or None, dokeum))
    for cp, dokeums in v2_dokeum.items():
        for seq, dokeum in enumerate(dokeums):
            rows.append((cp, seq, None, dokeum))
    dst.executemany("INSERT INTO character_hunum VALUES (?,?,?,?)", rows)
    dst.execute("CREATE INDEX idx_hunum_cp ON character_hunum(codepoint)")
    dst.commit()

    cps = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_hunum").fetchone()[0]
    with_jahun = dst.execute(
        "SELECT count(DISTINCT codepoint) FROM character_hunum "
        "WHERE jahun IS NOT NULL").fetchone()[0]
    log(f"[62]   character_hunum: {len(rows):,} rows, {cps:,} codepoints "
        f"({with_jahun:,} with 자훈)")

    v2.close()
    dst.close()
    log(f"[62] done: {DST_DB.name}")


if __name__ == "__main__":
    main()
