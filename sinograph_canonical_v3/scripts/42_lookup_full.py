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
    if st:
        rad = db.execute(
            "SELECT char, name_ko FROM radicals WHERE radical_idx=?",
            (st[0],)).fetchone() if st[0] else None
        out["structure"] = {
            "radical_idx": st[0], "total_strokes": st[1],
            "residual_strokes": st[2],
            "radical_char": rad[0] if rad else None,
            "radical_name": rad[1] if rad else None}
    else:
        out["structure"] = None

    # readings — five non-Korean languages
    by_type: dict[str, list[str]] = defaultdict(list)
    for rt, val in db.execute(
            "SELECT reading_type, value FROM character_readings "
            "WHERE codepoint=? ORDER BY rowid", (cp,)):
        by_type[rt].append(val)
    out["readings"] = {rt: by_type[rt] for rt, _ in READING_LABELS if by_type[rt]}

    # Korean 훈음 — (자훈, 독음) pairs from character_hunum
    out["hunum"] = [
        {"seq": seq, "jahun": jahun, "dokeum": dokeum}
        for seq, jahun, dokeum in db.execute(
            "SELECT seq, jahun, dokeum FROM character_hunum "
            "WHERE codepoint=? ORDER BY seq", (cp,))]

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
    for tcp, tch, scope, rel, cat in db.execute(
            "SELECT target_codepoint, target_character, relation_scope, "
            "relation, relation_category FROM variant_edges "
            "WHERE source_codepoint=? ORDER BY relation_category, relation",
            (cp,)):
        edges.append({"target": tch, "target_codepoint": tcp,
                      "scope": scope, "relation": rel, "category": cat})
    out["variant_edges"] = edges

    gcols = ["kr_grade", "kr_education", "cn_tonggyong", "jp_grade",
             "jp_freq", "jp_jlpt", "unihan_core"]
    grow = db.execute(
        "SELECT " + ",".join(gcols) + " FROM character_grades "
        "WHERE codepoint=?", (cp,)).fetchone()
    out["grades"] = dict(zip(gcols, grow)) if grow else None
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
        rad = str(s["radical_idx"])
        if s.get("radical_char"):
            rad += f" {s['radical_char']}"
        if s.get("radical_name"):
            rad += f" ({s['radical_name']})"
        print(f"  부수       : {rad}   "
              f"총획 {s['total_strokes']}   잔여획 {s['residual_strokes']}")

    print("  [발음]")
    if d["hunum"]:
        shown = ", ".join(
            (f"{h['jahun']} {h['dokeum']}" if h["jahun"] else h["dokeum"])
            for h in d["hunum"])
        print(f"  한국 훈음  : {shown}")
    for rt, label in READING_LABELS:
        vals = d["readings"].get(rt)
        if vals:
            print(f"  {_pad(label, 11)}: {' / '.join(vals)}")
    if not d["hunum"] and not d["readings"]:
        print("  (발음 정보 없음)")

    print("  [뜻]")
    if d["meanings"].get("ko"):
        print(f"  한국어     : {' / '.join(d['meanings']['ko'])}")
    if d["meanings"].get("en"):
        print(f"  영어       : {' / '.join(d['meanings']['en'])}")
    if not d["meanings"]:
        print("  (뜻 정보 없음)")

    print("  [이체자]")
    has_family = d["family"] and d["family"]["size"] > 1
    if has_family:
        members = " ".join(
            chr(int(m[2:], 16)) for m in d["family"]["members"]
            if int(m[2:], 16) < 0x110000)
        print(f"  family ({d['family']['size']}) : {members}")
    variants = [e for e in d["variant_edges"] if e["category"] == "variant"]
    related = [e for e in d["variant_edges"] if e["category"] == "semantic"]
    if variants:
        rels = ", ".join(
            f"{e['target']} [{e['relation']}]" for e in variants)
        print(f"  이체관계   : {rels}")
    if related:
        rels = ", ".join(
            f"{e['target']} [{e['relation']}]" for e in related)
        print(f"  관련어     : {rels}")
    if not has_family and not d["variant_edges"]:
        print("  (이체자 정보 없음)")

    print("  [급수]")
    g = d.get("grades")
    if g:
        parts = []
        if g.get("kr_grade"):
            parts.append(f"한자검정 {g['kr_grade']}")
        if g.get("kr_education"):
            parts.append(f"교육용 {g['kr_education']}")
        if g.get("cn_tonggyong") is not None:
            parts.append(f"통용규범 {g['cn_tonggyong']}급")
        if g.get("jp_grade") is not None:
            parts.append(f"일본학년 {g['jp_grade']}")
        if g.get("jp_freq") is not None:
            parts.append(f"일본빈도 {g['jp_freq']}위")
        if g.get("jp_jlpt") is not None:
            parts.append(f"JLPT {g['jp_jlpt']}급")
        if g.get("unihan_core"):
            parts.append(f"Unihan core {g['unihan_core']}")
        print("  " + "  /  ".join(parts) if parts else "  (급수 정보 없음)")
    else:
        print("  (급수 정보 없음)")


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
