# canonical_v3 — 앱 진입 전 DB 정리 결과

작성일: 2026-05-17. 이전: [36_CANONICAL_V3_COMPLETION.md](36_CANONICAL_V3_COMPLETION.md).
**이 문서의 §2 스키마가 canonical_v3 의 최종 형태다** — doc/36 §3 의 스키마는
이 정리로 대체됨.

## 0. 배경

doc/36 에서 canonical_v3 에 발음·뜻·이체자·훈음을 채웠다. Codex adversarial
review 와 자체 구조 점검에서 나온 정리 항목 중 **스키마에 손대는 것** 을
Tauri 뷰어 앱 작성 전에 끝냈다. 앱 코드를 짠 뒤 스키마를 바꾸면 쿼리를 다시
써야 하기 때문이다. 새 외부 데이터 (획순 / 자원 / 단어층) 는 범위 밖.

## 1. 정리한 6개 항목

| 항목 | 내용 |
|---|---|
| `character_hunum` 분리 | 한국 훈음(자훈+독음)을 `character_readings` 에서 빼내 전용 테이블로. 자훈↔독음 페어가 행 하나로 명시됨 |
| `character_summary` VIEW | 한 글자 핵심을 1행으로 — 앱이 3-테이블 join 안 해도 됨 |
| `radicals` 테이블 | 부수 idx(1-214) → 부수자·한글명·획수. 앱이 214 부수표를 하드코딩 안 해도 됨 |
| `relation_category` | `variant_edges` 에 컬럼 추가 — 진짜 이체자(`variant`) vs 의미관계(`semantic`) 구분 |
| `fts_search` FTS5 | 뜻·발음·훈으로 한자를 역검색 (예: "거울" → 鑑) |
| `idx_edges_tgt` | `variant_edges(target_codepoint)` 인덱스 — 역방향 조회용 |

## 2. 최종 스키마 — `canonical_v3.sqlite` (94 MB)

테이블 10개 + VIEW 1개.

| 테이블 | rows | 내용 |
|---|---:|---|
| `characters_ids` | 103,046 | IDS 분해 / top-IDC / 소스 합의 |
| `characters_structure` | 103,046 | radical_idx / total_strokes / residual_strokes |
| `characters_core` | 103,046 | codepoint / character / Unicode block |
| `character_readings` | 197,220 | codepoint / reading_type / value — **비한국어 5종** |
| `character_hunum` | 83,650 | codepoint / seq / jahun / dokeum — **한국 훈음** |
| `character_meanings` | 195,221 | codepoint / language(en,ko) / value |
| `variant_edges` | 88,704 | source·target / relation / **relation_category** / scope / sources_json / support_count |
| `variant_family` | 103,006 | codepoint / family_id / component_size / family_members_json / representative |
| `radicals` | 214 | radical_idx / char / name_ko / strokes |
| `fts_search` | 80,020 | FTS5 — codepoint / hanja / reading / hunum / meaning |
| `character_summary` (VIEW) | 103,046 | codepoint / character / block / radical_idx / total_strokes / residual_strokes / primary_ids / ids_top_idc |

핵심 변경:
- `character_readings.reading_type` ∈ {`mandarin`, `cantonese`, `onyomi`,
  `kunyomi`, `vietnamese`}. 한국어는 더 이상 여기 없음. `pair_group` 컬럼 삭제.
- 일본 발음 (`onyomi` / `kunyomi`) 은 **가나로만** 저장. v2 가 쓰던 Unihan
  레거시 로마자 필드 (`kJapaneseOn/Kun`, ~13%) 를 버리고 KANJIDIC2 가나 +
  Unihan `kJapanese` (가나) 로 재병합 → 커버리지 13% → **50%**, 로마자 0.
  상세는 §8.
- `character_hunum` — `seq` 가 다중 훈음 순서 (行 → seq0 다닐/행, seq1 항렬/항).
  `jahun` 은 nullable (getHunum 없이 독음만 있는 글자는 `jahun=NULL`).
  `dokeum` 은 항상 존재.
- `variant_edges.relation_category` — `variant` (같은 글자: traditional /
  simplified / dongja / sokja … 18종) / `semantic` (다른 글자의 유의·반의:
  ehanja_synonyms / ehanja_opposites).

## 3. 앱이 쓸 쿼리 패턴

```sql
-- 한 글자 핵심 (1행 fetch)
SELECT * FROM character_summary WHERE codepoint = ?;

-- 부수 상세
SELECT char, name_ko, strokes FROM radicals WHERE radical_idx = ?;

-- 발음 (비한국어 5종)
SELECT reading_type, value FROM character_readings WHERE codepoint = ?;

-- 한국 훈음 (자훈↔독음 페어, 순서 보존)
SELECT seq, jahun, dokeum FROM character_hunum
  WHERE codepoint = ? ORDER BY seq;

-- 뜻
SELECT language, value FROM character_meanings WHERE codepoint = ?;

-- 이체자: 진짜 이체자와 관련어를 분리
SELECT target_character, relation, relation_category
  FROM variant_edges WHERE source_codepoint = ?;
SELECT family_members_json FROM variant_family WHERE codepoint = ?;

-- 역검색: 뜻·발음·훈으로 한자 찾기
SELECT codepoint, hanja FROM fts_search WHERE fts_search MATCH ?;
-- 컬럼 지정: 뜻만 / 발음만
SELECT codepoint, hanja FROM fts_search WHERE meaning MATCH ?;
SELECT codepoint, hanja FROM fts_search WHERE reading MATCH ?;
```

## 4. 빌드 체인

스크립트 실행 순서 (생성 번호 ≠ 실행 순서 — 63/64 는 성격상 마지막):

```
python sinograph_canonical_v3/scripts/60_init_canonical_v3.py
python sinograph_canonical_v3/scripts/61_migrate_lexical_from_v2.py
python sinograph_canonical_v3/scripts/62_merge_hunum.py
python sinograph_canonical_v3/scripts/67_merge_japanese.py
python sinograph_canonical_v3/scripts/65_build_radicals.py
python sinograph_canonical_v3/scripts/66_build_app_layer.py
python sinograph_canonical_v3/scripts/63_coverage_report.py
python sinograph_canonical_v3/scripts/64_validate_canonical_v3.py
```

| 스크립트 | 역할 |
|---|---|
| 60 | 구조 2테이블 복사 + `characters_core` |
| 61 | v2 → readings(중·광·월 3종) / meanings / variant_edges(+category) / variant_family |
| 62 | e-hanja getHunum + v2 독음 → `character_hunum` (멱등) |
| 67 | KANJIDIC2 + Unihan kJapanese → `onyomi` / `kunyomi` 가나 재병합 (멱등) — §8 |
| 65 | `radicals` 테이블 |
| 66 | `character_summary` VIEW + `fts_search` FTS5 |
| 63 | 커버리지 리포트 → `out/canonical_v3_coverage.json` |
| 64 | 무결성 검증 24종 — 실패 시 non-zero exit |

조회 CLI: `python sinograph_canonical_v3/scripts/42_lookup_full.py --char 鑑`.

## 5. 커버리지 (universe 103,046, 실측)

| 항목 | 커버리지 |
|---|---:|
| 구조 (부수/획수/IDS) | 99.9%+ |
| 발음 비한국어 (하나라도) | 63.41% |
| └ onyomi (일본 음독) | 48.81% |
| └ kunyomi (일본 훈독) | 12.85% |
| └ mandarin / cantonese / vietnamese | 43.32% / 29.05% / 15.40% |
| 한국 훈음 — 독음 | 73.45% |
| 한국 훈음 — 자훈 | 50.63% |
| 뜻 (하나라도) | 74.48% |
| 이체자 edge 보유 | 41.94% (진짜 이체자 41.34%, 의미관계 3.38%) |

한국어가 `character_hunum` 으로 분리됐어도 발음 그룹 수치가 doc/36 보다
오히려 높은 것은 일본 발음 재병합 (§8) 으로 onyomi 가 13% → 49% 로 뛴
덕분이다.

## 6. 검증 — 통과

`64_validate_canonical_v3.py` 24종 전부 PASS:
- universe 폐쇄 (edge·family·lexical orphan 0)
- `character_readings` 에 한국어 reading_type 없음, 중복 tuple 0
- `onyomi` / `kunyomi` 가 가나 (로마자 0)
- `character_hunum` — dokeum 항상 존재, seq 정합, 중복 0
- `relation_category` ∈ {variant, semantic}
- `radicals` 214행 idx 1-214 완비
- `fts_search` 채워짐, `character_summary` == universe

추가 확인:
- `62` / `67` 2회 실행 → 행수 불변 (DROP 후 재생성, 멱등).
- `42_lookup_full.py --char 鑑` → 부수 "167 金 (쇠금部)", 훈음 "거울 감",
  음독 "カン" (가나), 이체관계/관련어 분리 표시. `--char 行` → "다닐 행, 항렬 항".
- FTS: `MATCH '거울'` / `MATCH 'mirror'` → 鑑 포함.

## 7. 범위 밖 (다음 phase)

- 획순 / per-stroke 데이터 (KanjiVG·MMH SVG) — `characters_stroke_level`
- 자원(字源) — 형성/회의/상형 분류
- 단어/숙어 레이어 (CEDICT·MOE 사전)

canonical_v3 는 단자(單字) 사전 앱 백엔드로 정리 완료. 다음은
`unihan_graph_viewer` (Tauri 2 + Rust) 를 이 DB 위에 재작성하는 phase.

## 8. 일본 발음 가나 재병합 (`67_merge_japanese.py`)

정리 직후 일본 발음이 표기·커버리지 양쪽에서 부실하다는 점이 드러나 별도로
손봤다.

**문제**: v2 는 일본 발음을 Unihan 의 **레거시 필드** `kJapaneseOn` /
`kJapaneseKun` 에서 가져왔다. 이 필드는 (1) **대문자 로마자** 표기, (2)
universe 의 13% 만 커버, (3) 여러 발음을 한 칸에 공백으로 몰아넣음. KANJIDIC2
(가나) 와 섞이면서 글자마다 카타카나 / 히라가나 / 로마자가 뒤죽박죽이었다.

**원인**: Unihan 에는 더 새로운 `kJapanese` 통합 필드가 있다 — **가나** 표기,
51,583 codepoint (50%), 음독(카타카나) + 훈독(히라가나) 을 한 필드에. v2 가
이 필드를 안 쓰고 작은 레거시 필드를 골랐던 것.

**해결** (`67_merge_japanese.py`): `onyomi` / `kunyomi` 를 두 가나-native
소스에서 재병합한다.
- **KANJIDIC2** `ja_on`(카타카나) / `ja_kun`(히라가나) — 우선 소스. 발음당
  한 행, 오쿠리가나 `.` 표기 유지.
- **Unihan `kJapanese`** — KANJIDIC2 가 커버 안 한 codepoint 를 채움. 공백
  분리 토큰을 script 로 분류 (히라가나 있으면 kunyomi, 아니면 onyomi).

**결과**:
- 일본 발음 커버리지 13.09% → **50.14%** (+38,179 codepoint).
- 표기 100% 가나, 로마자 0 (`64` 가 검증).
- 소실: 142 codepoint — 대부분 중국 간화자로, 일본어에서 안 쓰여 Unihan 이
  붙였던 발음 자체가 의심스러운 데이터. 버리는 게 정확.
- `character_readings` 에서 v2 의 `japanese_on/kun` 매핑 제거 (`61`),
  Japanese 는 이제 db_src 에서 직접 빌드.
