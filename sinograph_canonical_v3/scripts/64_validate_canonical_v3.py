"""canonical_v3 completion — final step: integrity validation.

Build-failing checks over `canonical_v3.sqlite`. Exits non-zero if any
check fails, so it gates the build chain. Covers universe closure,
duplicate rows, hunum shape, radicals, relation categories and the FTS /
view app layer.

Run last in the chain (after 60-66):
  python sinograph_canonical_v3/scripts/64_validate_canonical_v3.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DST_DB = Path(__file__).resolve().parents[1] / "out" / "canonical_v3.sqlite"

ALLOWED_READING_TYPES = {
    "mandarin", "cantonese", "onyomi", "kunyomi", "vietnamese"}
ALLOWED_LANGUAGES = {"en", "ko"}
ALLOWED_RELATION_CATEGORIES = {"variant", "semantic"}


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[64] run 60-66 first — not found: {DST_DB}")
    db = sqlite3.connect(f"file:{DST_DB}?mode=ro", uri=True)
    n = db.execute("SELECT count(*) FROM characters_ids").fetchone()[0]

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        log(f"  [{'PASS' if ok else 'FAIL'}] {name}"
            + (f"  — {detail}" if detail else ""))
        if not ok:
            failures.append(f"{name}: {detail}")

    def scalar(sql: str) -> int:
        return db.execute(sql).fetchone()[0]

    log("=" * 64)
    log(f"  canonical_v3 integrity validation  (universe {n:,})")
    log("=" * 64)

    # C1 — structure / core tables aligned on the universe
    for t in ("characters_structure", "characters_core"):
        c = scalar(f"SELECT count(*) FROM {t}")
        check(f"{t} row count == universe", c == n, f"{c:,} vs {n:,}")

    # C2 — variant_edges endpoints all in universe
    for col in ("source_codepoint", "target_codepoint"):
        bad = scalar(f"SELECT count(*) FROM variant_edges WHERE {col} "
                     "NOT IN (SELECT codepoint FROM characters_ids)")
        check(f"variant_edges {col} in universe", bad == 0, f"{bad} bad")

    # C3 — variant_family closed over universe, size matches members
    bad_member = bad_rep = bad_size = 0
    universe = {r[0] for r in db.execute("SELECT codepoint FROM characters_ids")}
    for cp, size, mj, rep in db.execute(
            "SELECT codepoint, component_size, family_members_json, "
            "representative FROM variant_family"):
        members = json.loads(mj)
        if any(m not in universe for m in members):
            bad_member += 1
        if rep not in universe:
            bad_rep += 1
        if size != len(members):
            bad_size += 1
    check("variant_family members in universe", bad_member == 0,
          f"{bad_member} rows")
    check("variant_family representative in universe", bad_rep == 0,
          f"{bad_rep} rows")
    check("variant_family component_size == len(members)", bad_size == 0,
          f"{bad_size} rows")

    # C4 — no duplicate readings (rerun / idempotency canary)
    dups = scalar(
        "SELECT count(*) FROM (SELECT codepoint, reading_type, value "
        "FROM character_readings GROUP BY codepoint, reading_type, value "
        "HAVING count(*) > 1)")
    check("character_readings has no exact duplicate", dups == 0,
          f"{dups} duplicated tuples")

    # C5 — reading_type / language vocabularies (Korean must NOT be here)
    rts = {r[0] for r in db.execute(
        "SELECT DISTINCT reading_type FROM character_readings")}
    check("reading_type vocabulary (no Korean in readings)",
          rts <= ALLOWED_READING_TYPES,
          f"unexpected: {sorted(rts - ALLOWED_READING_TYPES)}")
    langs = {r[0] for r in db.execute(
        "SELECT DISTINCT language FROM character_meanings")}
    check("meaning language vocabulary", langs <= ALLOWED_LANGUAGES,
          f"unexpected: {sorted(langs - ALLOWED_LANGUAGES)}")

    # C5b — onyomi / kunyomi must be kana, never romaji
    romaji_ja = scalar(
        "SELECT count(*) FROM character_readings "
        "WHERE reading_type IN ('onyomi','kunyomi') "
        "AND value GLOB '*[A-Za-z]*'")
    check("onyomi/kunyomi are kana (no romaji)", romaji_ja == 0,
          f"{romaji_ja} romaji values")

    # C6 — character_hunum shape
    null_dokeum = scalar(
        "SELECT count(*) FROM character_hunum WHERE dokeum IS NULL")
    check("character_hunum dokeum always present", null_dokeum == 0,
          f"{null_dokeum} rows with NULL dokeum")
    bad_seq = scalar(
        "SELECT count(*) FROM character_hunum WHERE seq IS NULL OR seq < 0")
    check("character_hunum seq is a non-negative integer", bad_seq == 0,
          f"{bad_seq} bad seq")
    hunum_dups = scalar(
        "SELECT count(*) FROM (SELECT codepoint, seq, jahun, dokeum "
        "FROM character_hunum GROUP BY codepoint, seq, jahun, dokeum "
        "HAVING count(*) > 1)")
    check("character_hunum has no exact duplicate", hunum_dups == 0,
          f"{hunum_dups} duplicated rows")

    # C7 — relation_category vocabulary
    cats = {r[0] for r in db.execute(
        "SELECT DISTINCT relation_category FROM variant_edges")}
    check("variant_edges relation_category vocabulary",
          cats <= ALLOWED_RELATION_CATEGORIES,
          f"unexpected: {sorted(cats - ALLOWED_RELATION_CATEGORIES)}")

    # C8 — radicals: 214 rows, idx 1-214 complete
    rad_n = scalar("SELECT count(*) FROM radicals")
    rad_range = scalar(
        "SELECT count(*) FROM radicals WHERE radical_idx BETWEEN 1 AND 214")
    check("radicals has 214 rows", rad_n == 214, f"{rad_n} rows")
    check("radicals idx all within 1-214", rad_range == rad_n,
          f"{rad_n - rad_range} out of range")

    # C9 — no orphan lexical / hunum rows
    for t in ("character_readings", "character_hunum",
              "character_meanings", "variant_family"):
        orphan = scalar(
            f"SELECT count(*) FROM {t} WHERE codepoint NOT IN "
            "(SELECT codepoint FROM characters_ids)")
        check(f"{t} has no orphan codepoint", orphan == 0, f"{orphan} orphans")

    # C10 — app layer present
    fts_n = scalar("SELECT count(*) FROM fts_search")
    fts_orphan = scalar(
        "SELECT count(*) FROM fts_search WHERE codepoint NOT IN "
        "(SELECT codepoint FROM characters_ids)")
    check("fts_search populated", fts_n > 0, f"{fts_n} rows")
    check("fts_search has no orphan codepoint", fts_orphan == 0,
          f"{fts_orphan} orphans")
    summary_n = scalar("SELECT count(*) FROM character_summary")
    check("character_summary VIEW == universe", summary_n == n,
          f"{summary_n:,} vs {n:,}")

    db.close()
    log("-" * 64)
    if failures:
        log(f"[64] VALIDATION FAILED — {len(failures)} check(s):")
        for f in failures:
            log(f"  - {f}")
        sys.exit(1)
    log("[64] all checks passed.")


if __name__ == "__main__":
    main()
