"""canonical_v3 completion — step 5: integrity validation.

Build-failing checks over `canonical_v3.sqlite`. Exits non-zero if any
check fails, so it can gate the build chain. Covers the issues raised in
the adversarial review: foreign-universe references, duplicate readings,
hunum pairing, orphan lexical rows.

Run (after 60 / 61 / 62 / 63):
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
    "mandarin", "cantonese", "onyomi", "kunyomi", "vietnamese",
    "dokeum", "jahun"}
ALLOWED_LANGUAGES = {"en", "ko"}


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    if not DST_DB.exists():
        raise SystemExit(f"[64] run 60-63 first — not found: {DST_DB}")
    db = sqlite3.connect(f"file:{DST_DB}?mode=ro", uri=True)
    universe = {r[0] for r in db.execute("SELECT codepoint FROM characters_ids")}
    n = len(universe)

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        log(f"  [{mark}] {name}" + (f"  — {detail}" if detail else ""))
        if not ok:
            failures.append(f"{name}: {detail}")

    log("=" * 64)
    log(f"  canonical_v3 integrity validation  (universe {n:,})")
    log("=" * 64)

    # C1 — structure tables aligned on the universe
    for t in ("characters_structure", "characters_core"):
        c = db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        check(f"{t} row count == universe", c == n, f"{c:,} vs {n:,}")

    # C2 — variant_edges endpoints are all in the universe
    bad_src = db.execute(
        "SELECT count(*) FROM variant_edges WHERE source_codepoint NOT IN "
        "(SELECT codepoint FROM characters_ids)").fetchone()[0]
    bad_tgt = db.execute(
        "SELECT count(*) FROM variant_edges WHERE target_codepoint NOT IN "
        "(SELECT codepoint FROM characters_ids)").fetchone()[0]
    check("variant_edges source in universe", bad_src == 0, f"{bad_src} bad")
    check("variant_edges target in universe", bad_tgt == 0, f"{bad_tgt} bad")

    # C3 — variant_family members + representative in the universe,
    #      component_size matches the stored member list
    bad_member = bad_rep = bad_size = 0
    for cp, fid, size, mj, rep in db.execute(
            "SELECT codepoint, family_id, component_size, "
            "family_members_json, representative FROM variant_family"):
        members = json.loads(mj)
        if any(m not in universe for m in members):
            bad_member += 1
        if rep not in universe:
            bad_rep += 1
        if size != len(members):
            bad_size += 1
    check("variant_family members in universe", bad_member == 0,
          f"{bad_member} rows with foreign member")
    check("variant_family representative in universe", bad_rep == 0,
          f"{bad_rep} rows")
    check("variant_family component_size == len(members)", bad_size == 0,
          f"{bad_size} rows")

    # C4 — no duplicate readings (the rerun / idempotency canary)
    dups = db.execute(
        "SELECT count(*) FROM (SELECT codepoint, reading_type, value, "
        "pair_group FROM character_readings GROUP BY codepoint, reading_type, "
        "value, pair_group HAVING count(*) > 1)").fetchone()[0]
    check("character_readings has no exact duplicate", dups == 0,
          f"{dups} duplicated reading tuples")

    # C5 — reading_type / language vocabularies
    rts = {r[0] for r in db.execute(
        "SELECT DISTINCT reading_type FROM character_readings")}
    check("reading_type vocabulary", rts <= ALLOWED_READING_TYPES,
          f"unexpected: {sorted(rts - ALLOWED_READING_TYPES)}")
    langs = {r[0] for r in db.execute(
        "SELECT DISTINCT language FROM character_meanings")}
    check("meaning language vocabulary", langs <= ALLOWED_LANGUAGES,
          f"unexpected: {sorted(langs - ALLOWED_LANGUAGES)}")

    # C6 — hunum pairing: jahun always paired; at most one jahun + one
    #      dokeum per (codepoint, pair_group)
    jahun_unpaired = db.execute(
        "SELECT count(*) FROM character_readings "
        "WHERE reading_type='jahun' AND pair_group IS NULL").fetchone()[0]
    check("jahun rows always have pair_group", jahun_unpaired == 0,
          f"{jahun_unpaired} unpaired jahun")
    overfilled = db.execute(
        "SELECT count(*) FROM (SELECT codepoint, pair_group, reading_type "
        "FROM character_readings WHERE pair_group IS NOT NULL "
        "GROUP BY codepoint, pair_group, reading_type HAVING count(*) > 1)"
    ).fetchone()[0]
    check("<=1 jahun and <=1 dokeum per pair_group", overfilled == 0,
          f"{overfilled} over-filled pair slots")

    # C7 — no orphan lexical rows
    for t, col in (("character_readings", "codepoint"),
                   ("character_meanings", "codepoint"),
                   ("variant_family", "codepoint")):
        orphan = db.execute(
            f"SELECT count(*) FROM {t} WHERE {col} NOT IN "
            "(SELECT codepoint FROM characters_ids)").fetchone()[0]
        check(f"{t} has no orphan codepoint", orphan == 0, f"{orphan} orphans")

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
