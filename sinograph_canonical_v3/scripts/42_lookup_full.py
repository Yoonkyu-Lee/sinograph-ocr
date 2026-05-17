"""canonical_v3 — full dictionary lookup.

One codepoint -> structure + readings + meanings + 훈음 + variants, joined
across the 7 tables of `canonical_v3.sqlite`. This is the dictionary view;
`40_lookup.py` stays as the structure-only IDS view.

Usage:
  python sinograph_canonical_v3/scripts/42_lookup_full.py --char 鑑
  python sinograph_canonical_v3/scripts/42_lookup_full.py --cp U+9451
  python sinograph_canonical_v3/scripts/42_lookup_full.py --char 鑑 --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_DB = Path(__file__).resolve().parents[1] / "out" / "canonical_v3.sqlite"

# reading_type -> display label, in display order
READING_LABELS = [
    ("mandarin", "표준중국어"),
    ("cantonese", "광동어"),
    ("onyomi", "일본 음독"),
    ("kunyomi", "일본 훈독"),
    ("vietnamese", "베트남어"),
]


def normalize_cp(s: str) -> str:
    s = s.strip().upper()
    if s.startswith("U+"):
        s = s[2:]
    return f"U+{int(s, 16):04X}"


def fetch(db: sqlite3.Connection, cp: str) -> dict:
    out: dict = {"codepoint": cp}

    core = db.execute(
        "SELECT character, block FROM characters_core WHERE codepoint=?",
        (cp,)).fetchone()
    out["character"] = core[0] if core else (
        chr(int(cp[2:], 16)) if int(cp[2:], 16) < 0x110000 else "?")
    out["block"] = core[1] if core else None

    ids = db.execute(
        "SELECT primary_ids, ids_top_idc FROM characters_ids WHERE codepoint=?",
        (cp,)).fetchone()
    out["ids"] = {"decomposition": ids[0], "top_idc": ids[1]} if ids else None

    st = db.execute(
        "SELECT radical_idx, total_strokes, residual_strokes "
        "FROM characters_structure WHERE codepoint=?", (cp,)).fetchone()
    out["structure"] = (
        {"radical_idx": st[0], "total_strokes": st[1],
         "residual_strokes": st[2]} if st else None)

    # readings — split into 훈음 pairs and plain readings
    by_type: dict[str, list[str]] = defaultdict(list)
    pairs: dict[int, dict] = defaultdict(dict)
    dokeum_solo: list[str] = []
    for rt, val, grp in db.execute(
            "SELECT reading_type, value, pair_group FROM character_readings "
            "WHERE codepoint=? ORDER BY pair_group, rowid", (cp,)):
        if rt in ("jahun", "dokeum") and grp is not None:
            pairs[grp][rt] = val
        elif rt == "dokeum":
            dokeum_solo.append(val)
        else:
            by_type[rt].append(val)
    out["hunum"] = [
        {"jahun": pairs[g].get("jahun", ""), "dokeum": pairs[g].get("dokeum", "")}
        for g in sorted(pairs)]
    out["dokeum_unpaired"] = dokeum_solo
    out["readings"] = {rt: by_type[rt] for rt, _ in READING_LABELS if by_type[rt]}

    meanings: dict[str, list[str]] = defaultdict(list)
    for lang, val in db.execute(
            "SELECT language, value FROM character_meanings WHERE codepoint=?",
            (cp,)):
        meanings[lang].append(val)
    out["meanings"] = dict(meanings)

    fam = db.execute(
        "SELECT family_id, component_size, family_members_json, representative "
        "FROM variant_family WHERE codepoint=?", (cp,)).fetchone()
    out["family"] = (
        {"family_id": fam[0], "size": fam[1],
         "members": json.loads(fam[2]), "representative": fam[3]}
        if fam else None)

    edges = []
    for tcp, tch, scope, rel in db.execute(
            "SELECT target_codepoint, target_character, relation_scope, relation "
            "FROM variant_edges WHERE source_codepoint=? ORDER BY relation_scope",
            (cp,)):
        edges.append({"target": tch, "target_codepoint": tcp,
                      "scope": scope, "relation": rel})
    out["variant_edges"] = edges
    return out


def _disp_width(s: str) -> int:
    """Rough monospace display width — CJK / Hangul count as 2 columns."""
    return sum(2 if ord(c) > 0x1100 else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _disp_width(s))


def pretty(d: dict) -> None:
    line = "=" * 60
    blk = f"   ({d['block']})" if d.get("block") else ""
    print(line)
    print(f"  {d['character']}   {d['codepoint']}{blk}")
    print(line)

    print("  [구조]")
    if d["ids"]:
        print(f"  IDS 분해   : {d['ids']['decomposition']}   "
              f"(top-IDC {d['ids']['top_idc']})")
    if d["structure"]:
        s = d["structure"]
        print(f"  부수       : {s['radical_idx']}   "
              f"총획 {s['total_strokes']}   잔여획 {s['residual_strokes']}")

    print("  [발음]")
    if d["hunum"]:
        shown = ", ".join(
            f"{h['jahun']} {h['dokeum']}".strip() for h in d["hunum"])
        print(f"  한국 훈음  : {shown}")
    elif d["dokeum_unpaired"]:
        print(f"  한국 독음  : {' / '.join(d['dokeum_unpaired'])}")
    for rt, label in READING_LABELS:
        vals = d["readings"].get(rt)
        if vals:
            print(f"  {_pad(label, 11)}: {' / '.join(vals)}")
    if not d["hunum"] and not d["dokeum_unpaired"] and not d["readings"]:
        print("  (발음 정보 없음)")

    print("  [뜻]")
    if d["meanings"].get("ko"):
        print(f"  한국어     : {' / '.join(d['meanings']['ko'])}")
    if d["meanings"].get("en"):
        print(f"  영어       : {' / '.join(d['meanings']['en'])}")
    if not d["meanings"]:
        print("  (뜻 정보 없음)")

    print("  [이체자]")
    if d["family"] and d["family"]["size"] > 1:
        members = " ".join(
            chr(int(m[2:], 16)) for m in d["family"]["members"]
            if int(m[2:], 16) < 0x110000)
        print(f"  family ({d['family']['size']}) : {members}")
    if d["variant_edges"]:
        rels = ", ".join(
            f"{e['target']} [{e['relation']}]" for e in d["variant_edges"])
        print(f"  관계       : {rels}")
    if not (d["family"] and d["family"]["size"] > 1) and not d["variant_edges"]:
        print("  (이체자 정보 없음)")


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cp", help="codepoint (U+XXXX or raw hex)")
    g.add_argument("--char", help="literal character")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cp = (f"U+{ord(args.char[0]):04X}" if args.char
          else normalize_cp(args.cp))
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    in_universe = db.execute(
        "SELECT 1 FROM characters_ids WHERE codepoint=?", (cp,)).fetchone()
    if not in_universe:
        print(f"[lookup] {cp} not in canonical_v3 universe")
        sys.exit(1)
    data = fetch(db, cp)
    db.close()

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        pretty(data)


if __name__ == "__main__":
    main()
