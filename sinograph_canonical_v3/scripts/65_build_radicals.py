"""canonical_v3 completion — step 4: build the radicals reference table.

`characters_structure.radical_idx` is a bare 1-214 number. To show
"부수 167 金 (쇠금部)" the app would otherwise hard-code the 214 Kangxi
radicals. This builds a small reference table instead.

`radicals(radical_idx, char, name_ko, strokes)`:
  - char    : the radical character (e.g. 金)
  - name_ko : Korean radical name from e-hanja (e.g. 쇠금部)
  - strokes : the radical character's own total stroke count

Source: e-hanja online detail.jsonl `radical.char` / `radical.name`,
keyed to radical_idx through `characters_structure`. Stroke count comes
from `characters_structure.total_strokes` of the radical character.

Run (after 60 / 61 / 62):
  python sinograph_canonical_v3/scripts/65_build_radicals.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DST_DB = ROOT / "sinograph_canonical_v3" / "out" / "canonical_v3.sqlite"
DETAIL_JSONL = ROOT / "db_src" / "e-hanja_online" / "detail.jsonl"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[65] run 60-62 first — not found: {DST_DB}")
    if not DETAIL_JSONL.exists():
        raise SystemExit(f"[65] not found: {DETAIL_JSONL}")

    dst = sqlite3.connect(DST_DB)

    # codepoint -> radical_idx, and codepoint -> own stroke count
    cp_radical = {cp: idx for cp, idx in dst.execute(
        "SELECT codepoint, radical_idx FROM characters_structure "
        "WHERE radical_idx IS NOT NULL")}
    cp_strokes = {cp: ts for cp, ts in dst.execute(
        "SELECT codepoint, total_strokes FROM characters_structure "
        "WHERE total_strokes IS NOT NULL")}
    log(f"[65] radical_idx map: {len(cp_radical):,} codepoints")

    # idx -> Counter of (radical_char, radical_name) seen in e-hanja
    votes: dict[int, Counter] = defaultdict(Counter)
    scanned = 0
    with open(DETAIL_JSONL, encoding="utf-8") as f:
        for line in f:
            scanned += 1
            d = json.loads(line)
            ch = d.get("char")
            rad = d.get("radical")
            if not ch or not rad:
                continue
            cp = f"U+{ord(ch[0]):04X}"
            idx = cp_radical.get(cp)
            rchar = (rad.get("char") or "").strip()
            rname = (rad.get("name") or "").strip()
            if idx and rchar:
                votes[idx][(rchar, rname)] += 1
    log(f"[65] scanned {scanned:,} detail rows; "
        f"{len(votes)} of 214 radicals have e-hanja data")

    dst.execute("DROP TABLE IF EXISTS main.radicals")
    dst.execute(
        "CREATE TABLE radicals ("
        "radical_idx INTEGER PRIMARY KEY, char TEXT, "
        "name_ko TEXT, strokes INTEGER)")
    rows, missing = [], []
    for idx in range(1, 215):
        if idx not in votes:
            missing.append(idx)
            rows.append((idx, None, None, None))
            continue
        (rchar, rname), _ = votes[idx].most_common(1)[0]
        rcp = f"U+{ord(rchar[0]):04X}" if rchar else None
        strokes = cp_strokes.get(rcp)
        rows.append((idx, rchar, rname or None, strokes))
    dst.executemany("INSERT INTO radicals VALUES (?,?,?,?)", rows)
    dst.commit()

    have_strokes = sum(1 for *_, s in rows if s is not None)
    log(f"[65] radicals: 214 rows  "
        f"({214 - len(missing)} with char/name, {have_strokes} with strokes)")
    if missing:
        log(f"[65]   (no e-hanja data for radical idx: {missing})")
    # sample
    for idx in (1, 9, 167, 214):
        r = dst.execute("SELECT * FROM radicals WHERE radical_idx=?",
                         (idx,)).fetchone()
        log(f"[65]   {r}")

    dst.close()
    log(f"[65] done: {DST_DB.name}")


if __name__ == "__main__":
    main()
