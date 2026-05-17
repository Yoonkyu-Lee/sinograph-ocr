"""canonical_v3 completion — step 2: migrate lexical tables from v2.

canonical_v2 already merged db_src (Unihan / e-hanja online / KANJIDIC2 /
MMH) into readings, meanings and a variant graph. This script ports those
four tables into `canonical_v3.sqlite`, restricted to the v3 universe
(codepoints in `characters_ids`).

Field renames applied here:
  reading_type japanese_on   -> onyomi
  reading_type japanese_kun  -> kunyomi
  reading_type korean_hangul -> dokeum   (한국 한자음 = 독음)
mandarin / cantonese / vietnamese keep their names. `jahun` (자훈) is added
later by 62_merge_hunum.py.

The v2 file is opened read-only and never ATTACH-ed, so no DDL here can
reach it.

Run (after 60_init_canonical_v3.py):
  python sinograph_canonical_v3/scripts/61_migrate_lexical_from_v2.py
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

# v2 reading_type -> v3 reading_type
READING_TYPE_MAP = {
    "mandarin": "mandarin",
    "cantonese": "cantonese",
    "vietnamese": "vietnamese",
    "japanese_on": "onyomi",
    "japanese_kun": "kunyomi",
    "korean_hangul": "dokeum",
}

# v2 variant-edge source tokens that are allowed. e-hanja MUST be the online
# DB; the mobile DB (ejajeon) must never appear.
ALLOWED_EDGE_SOURCES = {"unihan", "ehanja_online", "kanjidic2", "makemeahanzi"}


def log(msg: str) -> None:
    print(msg, flush=True)


def create_tables(dst: sqlite3.Connection) -> None:
    for name in ("character_readings", "character_meanings",
                 "variant_edges", "variant_family"):
        dst.execute(f"DROP TABLE IF EXISTS main.{name}")
    dst.execute(
        "CREATE TABLE character_readings ("
        "codepoint TEXT, reading_type TEXT, value TEXT, pair_group INTEGER)")
    dst.execute(
        "CREATE TABLE character_meanings ("
        "codepoint TEXT, language TEXT, value TEXT)")
    dst.execute(
        "CREATE TABLE variant_edges ("
        "source_codepoint TEXT, source_character TEXT, "
        "target_codepoint TEXT, target_character TEXT, "
        "relation_scope TEXT, relation TEXT, "
        "sources_json TEXT, support_count INTEGER)")
    dst.execute(
        "CREATE TABLE variant_family ("
        "codepoint TEXT PRIMARY KEY, family_id INTEGER, "
        "component_size INTEGER, family_members_json TEXT, "
        "representative TEXT)")


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[61] run 60_init first — not found: {DST_DB}")
    if not V2_DB.exists():
        raise SystemExit(f"[61] not found: {V2_DB}")

    dst = sqlite3.connect(DST_DB)
    v2 = sqlite3.connect(f"file:{V2_DB}?mode=ro", uri=True)

    universe = {r[0] for r in dst.execute("SELECT codepoint FROM characters_ids")}
    log(f"[61] v3 universe: {len(universe):,} codepoints")

    create_tables(dst)

    # --- readings ---
    log("[61] migrating character_readings ...")
    rd_rows, skipped_rt = [], set()
    for cp, rt, val in v2.execute(
            "SELECT codepoint, reading_type, value FROM character_readings"):
        if cp not in universe:
            continue
        mapped = READING_TYPE_MAP.get(rt)
        if mapped is None:
            skipped_rt.add(rt)
            continue
        rd_rows.append((cp, mapped, val, None))
    dst.executemany("INSERT INTO character_readings VALUES (?,?,?,?)", rd_rows)
    log(f"[61]   readings: {len(rd_rows):,} rows")
    if skipped_rt:
        log(f"[61]   (note: unmapped reading_type skipped: {sorted(skipped_rt)})")
    for rt in sorted(set(READING_TYPE_MAP.values())):
        n = dst.execute("SELECT count(DISTINCT codepoint) FROM character_readings "
                         "WHERE reading_type=?", (rt,)).fetchone()[0]
        log(f"[61]     {rt:<11s}: {n:,} codepoints")

    # --- meanings ---
    log("[61] migrating character_meanings ...")
    mn_rows = [(cp, lang, val) for cp, lang, val in v2.execute(
        "SELECT codepoint, language, value FROM character_meanings")
        if cp in universe]
    dst.executemany("INSERT INTO character_meanings VALUES (?,?,?)", mn_rows)
    log(f"[61]   meanings: {len(mn_rows):,} rows")

    # --- variant_edges ---
    log("[61] migrating variant_edges ...")
    edge_rows, all_tokens = [], set()
    dropped_edges = 0
    for (scp, sch, tcp, tch, scope, rel, sj, supp) in v2.execute(
            "SELECT source_codepoint, source_character, target_codepoint, "
            "target_character, relation_scope, relation, sources_json, "
            "support_count FROM variant_edges"):
        # both endpoints must be canonical v3 entries — an edge to a
        # codepoint the same DB cannot look up would be a dangling link.
        if scp not in universe or tcp not in universe:
            if scp in universe:
                dropped_edges += 1
            continue
        for tok in json.loads(sj):
            all_tokens.add(tok)
        edge_rows.append((scp, sch, tcp, tch, scope, rel, sj, supp))
    # provenance assert — e-hanja must be the online DB, never mobile.
    bad = all_tokens - ALLOWED_EDGE_SOURCES
    if bad or any("ejajeon" in t or "mobile" in t for t in all_tokens):
        raise SystemExit(f"[61] FAIL — unexpected edge source token(s): {bad}")
    dst.executemany("INSERT INTO variant_edges VALUES (?,?,?,?,?,?,?,?)", edge_rows)
    log(f"[61]   edges: {len(edge_rows):,} rows  "
        f"(dropped {dropped_edges:,} with out-of-universe target; "
        f"source tokens verified: {sorted(all_tokens)})")

    # --- variant_family (enriched graph: Unihan + e-hanja schoolCom) ---
    # Family members are closed over the v3 universe: out-of-universe members
    # are filtered out and component_size is recomputed afterwards, so the
    # stored size and members are all looked-up-able in this same DB.
    log("[61] migrating variant_family (enriched) ...")
    fam_raw, dropped_members = [], 0
    for cp, rep, members_json in v2.execute(
            "SELECT codepoint, enriched_representative_form, "
            "enriched_family_members_json FROM variant_components"):
        if cp not in universe:
            continue
        raw = json.loads(members_json) if members_json else [cp]
        members = sorted({m for m in raw if m in universe} | {cp})
        dropped_members += len(raw) - sum(1 for m in raw if m in universe)
        # representative falls back to the smallest in-universe member when
        # the v2 representative itself is outside the v3 universe. Members of
        # one family share the same filtered list, so the fallback is stable.
        rep = rep if rep in universe else members[0]
        fam_raw.append((cp, rep, members))
    # dense family_id keyed by representative
    rep_to_id = {rep: i for i, rep in
                 enumerate(sorted({r for _, r, _ in fam_raw}))}
    fam_rows = [(cp, rep_to_id[rep], len(members),
                 json.dumps(members, ensure_ascii=False), rep)
                for cp, rep, members in fam_raw]
    dst.executemany("INSERT INTO variant_family VALUES (?,?,?,?,?)", fam_rows)
    multi = sum(1 for *_, m, _, _ in fam_rows if m > 1)
    log(f"[61]   family: {len(fam_rows):,} rows, {len(rep_to_id):,} families, "
        f"{multi:,} codepoints in a family of 2+ "
        f"(dropped {dropped_members:,} out-of-universe member refs)")

    # --- indexes ---
    log("[61] building indexes ...")
    dst.execute("CREATE INDEX idx_readings_cp ON character_readings(codepoint)")
    dst.execute("CREATE INDEX idx_meanings_cp ON character_meanings(codepoint)")
    dst.execute("CREATE INDEX idx_edges_src ON variant_edges(source_codepoint)")
    dst.execute("CREATE INDEX idx_family_fid ON variant_family(family_id)")

    dst.commit()
    v2.close()
    dst.close()
    size_mb = DST_DB.stat().st_size / (1024 * 1024)
    log(f"[61] done: {DST_DB.name}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
