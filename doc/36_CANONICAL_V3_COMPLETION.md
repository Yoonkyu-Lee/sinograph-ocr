# canonical_v3 완성 — lexical 테이블 복구 결과

작성일: 2026-05-17. 계획: `.claude/plans` (canonical_v3 DB 완성).
이전 문서: [17_CANONICAL_V3_PLAN.md](17_CANONICAL_V3_PLAN.md),
[../sinograph_canonical_v3/BUILD_STATUS.md](../sinograph_canonical_v3/BUILD_STATUS.md).

## 0. 배경

lab3 최종 시연 목표는 한자 인식 모델 완성뿐이었다. 그래서 canonical_v3 는
학습 보조 레이블에 필요한 구조 정보 (IDS 분해 / 부수 / 획수) 만 담고 있었다.
목표가 Windows 사전/뷰어 응용 프로그램으로 바뀌면서, 화면에 보여줄 lexical
정보 (발음 / 뜻 / 이체관계 / 한국 훈음) 를 채워야 했다.

발음·뜻·이체자는 이미 canonical_v2 가 db_src (Unihan / e-hanja online /
KANJIDIC2 / MMH) 를 병합해 보유하고 있었다. 그래서 이 작업은 새 데이터
발굴이 아니라 **v2 의 lexical 테이블을 v3 universe·schema 로 이식**하는
것이었다. 한국 훈음 (자훈) 만 v2 에 없어 e-hanja online 에서 새로 파싱했다.

산출물: **`sinograph_canonical_v3/out/canonical_v3.sqlite`** (75 MB).
기존 `ids_merged.sqlite` (구조 빌드 중간물) 는 보존.

## 1. 완성 전 v3 가 가진 것

`ids_merged.sqlite`, universe 103,046 codepoint (BabelStone ∪ CHISE ∪
cjkvi-ids). 테이블 2개:

- `characters_ids` — IDS 분해 트리, top-IDC, 소스 합의, e-hanja 부품 대조
- `characters_structure` — 부수 인덱스 (1–214), 총획수, 잔여획수

발음·뜻·이체관계·훈음은 전혀 없었다.

## 2. 추가한 항목과 출처

| 항목 | 즉시 출처 | 원천 db_src 소스 |
|---|---|---|
| 발음 6종 (표준중국어 / 광동어 / 일본 음독 / 일본 훈독 / 베트남어 / 한국 독음) | v2 `character_readings` | Unihan k*, e-hanja online |
| 뜻 (영어 / 한국어) | v2 `character_meanings` | Unihan kDefinition, e-hanja getJahae |
| 이체자 edge (20종 관계) | v2 `variant_edges` | Unihan k*Variant 6종, e-hanja online getSchoolCom 10종 + detail 3종, KANJIDIC2 1종 |
| 이체자 family (enriched 그래프) | v2 `variant_components` | 위 edge 의 connected component |
| 한국 훈음 — 자훈(訓) | **신규 파싱** | e-hanja online `tree.jsonl` getHunum |

### 2.1 이체관계도 출처 검증

v2 `build_canonical_db_v2.py` 의 `build_variant_graph()` 검토 결과, 이체자
graph 의 e-hanja 부분은 **e-hanja online (`e-hanja_online/tree.jsonl` +
`detail.jsonl`)** 만 쓴다. e-hanja mobile (`db_src/e-hanja/ejajeon_plain.db`)
는 v2 빌드에서 참조하지 않는다. 이식 스크립트 (`61`) 는 `variant_edges` 의
`sources_json` 토큰이 `{unihan, ehanja_online, kanjidic2}` 안에만 있고
`ejajeon`/`mobile` 이 없음을 assert 로 재확인했다 — 통과.

### 2.2 훈음 — 자훈·독음 분리

한국 한자음은 자훈(訓: "거울") 과 독음(音: "감") 으로 나뉜다. v2 는 독음만
`korean_hangul` 로 가졌다. e-hanja online getHunum `hRead` 필드
(`"거울 감"` 형식) 를 콤마 분리 후 마지막 공백 기준으로 잘라 (자훈, 독음)
페어를 복원했다. 한 글자의 여러 훈음 (예: 行 → 다닐 행 / 항렬 항) 은
`pair_group` 으로 자훈↔독음 정렬을 보존한다.

reading_type 명명: `onyomi` (일본 음독), `kunyomi` (일본 훈독),
`dokeum` (한국 독음), `jahun` (한국 자훈). `mandarin` / `cantonese` /
`vietnamese` 는 유지.

## 3. 완성 DB 스펙 — `canonical_v3.sqlite`

테이블 7개. codepoint 하나로 join 하면 한 글자의 구조 + 발음 + 뜻 + 훈음 +
이체관계가 전부 나온다.

| 테이블 | rows | 내용 |
|---|---:|---|
| `characters_ids` | 103,046 | IDS 분해 / top-IDC / 소스 합의 (기존 v3) |
| `characters_structure` | 103,046 | 부수 / 총획 / 잔여획 (기존 v3) |
| `characters_core` | 103,046 | codepoint / character / Unicode block (신규 마스터) |
| `character_readings` | 278,815 | codepoint / reading_type / value / pair_group |
| `character_meanings` | 195,221 | codepoint / language (en, ko) / value |
| `variant_edges` | 88,704 | source·target codepoint+char / relation_scope / relation / sources_json / support_count |
| `variant_family` | 103,006 | codepoint / family_id / component_size / family_members_json / representative |

`variant_edges` 와 `variant_family` 는 v3 universe 안에서 닫혀 있다. edge 는
source·target 둘 다 `characters_ids` 에 있어야 보존하고 (out-of-universe
target 18건 제거), family member 도 universe 밖 참조 89건을 거른 뒤
`component_size` 를 재계산한다. 따라서 모든 이체자 참조는 같은 DB 안에서
조회 가능하다.

`character_readings.reading_type`: `mandarin`, `cantonese`, `onyomi`,
`kunyomi`, `vietnamese`, `dokeum`, `jahun`. `jahun`/`dokeum` 페어는
`pair_group` 정수로 묶이고, 나머지는 `pair_group = NULL`.

`variant_family` 는 enriched 그래프 (Unihan 이체자 + e-hanja schoolCom,
느슨한 의미관계 제외) 의 connected component 다. `variant_edges` 는 의미관계
(synonyms/opposites) 까지 포함한 전체 edge 를 relation 별로 보존한다.

조회 CLI: `python sinograph_canonical_v3/scripts/42_lookup_full.py --char 鑑`
(`--cp U+9451`, `--json` 지원). 구조 전용 CLI `40_lookup.py` 는 그대로 둠.

## 4. 정보 없음 / 빈 비율 (실측, universe 103,046)

`63_coverage_report.py` 출력. 원본: `out/canonical_v3_coverage.json`.

| 항목 | 보유 | 커버리지 | 빈 비율 |
|---|---:|---:|---:|
| 구조 — radical_idx | 102,960 | 99.92% | 0.08% |
| 구조 — total_strokes | 103,005 | 99.96% | 0.04% |
| 구조 — residual_strokes | 102,944 | 99.90% | 0.10% |
| 구조 — IDS 분해 | 103,046 | 100.00% | 0.00% |
| 발음 — 하나라도 | 78,275 | 75.96% | 24.04% |
| 발음 — 한국 독음 (dokeum) | 75,692 | 73.45% | 26.55% |
| 발음 — 한국 자훈 (jahun) | 52,177 | 50.63% | 49.37% |
| 발음 — 표준중국어 (mandarin) | 44,643 | 43.32% | 56.68% |
| 발음 — 광동어 (cantonese) | 29,936 | 29.05% | 70.95% |
| 발음 — 베트남어 (vietnamese) | 15,874 | 15.40% | 84.60% |
| 발음 — 일본 음독 (onyomi) | 13,292 | 12.90% | 87.10% |
| 발음 — 일본 훈독 (kunyomi) | 11,431 | 11.09% | 88.91% |
| 뜻 — 하나라도 | 76,752 | 74.48% | 25.52% |
| 뜻 — 한국어 (ko) | 75,692 | 73.45% | 26.55% |
| 뜻 — 영어 (en) | 23,696 | 23.00% | 77.00% |
| 이체자 — edge 보유 | 43,215 | 41.94% | 58.06% |
| 이체자 — family 멤버 2+ | 42,511 | 41.25% | 58.75% |

평균: 발음 보유 글자당 reading 약 2.7개, 뜻 보유 글자당 약 2.5개.

**왜 ~25% 가 비는가**: 발음·뜻 0인 약 25k 글자는 대부분 Ext G/H/I/J 의
희귀·역사 한자다. Unihan kMandarin (44k) · kDefinition (23k), e-hanja (76k)
등 모든 소스의 원천 커버리지 한계이지 누락이 아니다 — db_src 재병합으로도
못 채운다. 앱은 이런 글자에 "정보 없음" 을 표시한다 (`42_lookup_full.py`
에서 확인됨).

**universe 차이**: v2 가 v3 의 103,006 cp (99.96%) 를 커버. v3 에만 있는
40 cp 는 `variant_family` 행이 없고 lexical 값이 전부 NULL. v2 에만 있는
321 cp (CJK Radicals Supplement) 는 v3 universe 밖이라 이식하지 않았다.
별도로 `characters_core` 의 block 분류에서 40 cp 가 `(other)` 로 떨어지는데,
이는 IDS 소스가 가진 비-한자 기호 (Greek α, 원문자 ①, CJK Strokes 등) 로
universe 0.04% 다.

## 5. 빌드 체인

신규 스크립트는 `sinograph_canonical_v3/scripts/` 에 60번대로 추가.

| 스크립트 | 역할 |
|---|---|
| `60_init_canonical_v3.py` | 구조 2테이블 복사 + `characters_core` 생성 |
| `61_migrate_lexical_from_v2.py` | v2 → readings / meanings / variant_edges / variant_family 이식 |
| `62_merge_hunum.py` | e-hanja getHunum 파싱 → `jahun` + 페어 `dokeum` (멱등) |
| `63_coverage_report.py` | §4 커버리지 재계산 → JSON + stdout |
| `64_validate_canonical_v3.py` | 무결성 검증 — 실패 시 non-zero exit |
| `42_lookup_full.py` | 통합 사전 lookup CLI |

재현:
```
python sinograph_canonical_v3/scripts/60_init_canonical_v3.py
python sinograph_canonical_v3/scripts/61_migrate_lexical_from_v2.py
python sinograph_canonical_v3/scripts/62_merge_hunum.py
python sinograph_canonical_v3/scripts/63_coverage_report.py
python sinograph_canonical_v3/scripts/64_validate_canonical_v3.py
```

빌드 중 `ids_merged.sqlite` 의 `characters_ids` 가 한 번 손상돼 (ATTACH 된
DB 로 번진 비-한정 `DROP TABLE`), IDS 병합 체인 30→31→32→31→35 로 재생성해
복구했다. `ids_merged_stats.json` 의 기존 수치 (103,046 / agreement 분포)
와 재빌드 결과가 정확히 일치함을 확인했다. `60` 스크립트는 이후 source 를
ATTACH 하지 않고 read-only 별도 연결로 복사하도록 수정했다.

## 6. 검증된 것 / 안 된 것

**검증됨** (`64_validate_canonical_v3.py` 15개 체크 전부 PASS):
- 7테이블 모두 생성, row 수 §3 과 일치
- `variant_edges` 출처에 e-hanja mobile DB 없음 (assert 통과)
- variant edge·family 가 universe 안에서 닫힘 (foreign 참조 0)
- `character_readings` 중복 tuple 0, reading_type/language vocabulary 정상
- 훈음 자훈/독음 분리 + `pair_group` 정렬 (`鑑` → 거울 감, `行` → 다닐 행 / 항렬 항)
- Ext J 등 lexical 없는 글자에서 "정보 없음" 정상 표시
- 커버리지 표 §4 = `canonical_v3_coverage.json`

**adversarial review 반영** (Codex, 2026-05-17):
- variant edge·family 의 universe 폐쇄 — out-of-universe target 18건 / family
  member 89건 제거, `component_size` 재계산 후 저장 (`61`).
- `62_merge_hunum.py` 멱등화 — jahun·dokeum 을 함께 삭제 후 재삽입. `62` 를
  2회 실행해도 `character_readings` row 수 불변 (278,815) 확인.
- hunum 병합의 v2 독음 손실 우려 — 실측 결과 hunum 적용 54,699자 전부에서
  getHunum 독음 set 이 v2 korean_hangul 의 상위집합. **손실 0건** — 별도
  조치 불요.

**범위 밖 (이번에 안 함)**:
- 보조 색인 (cangjie / four-corner / phonetic class) — 사용자 결정으로 제외
- 교육급수 / JLPT / 빈도 — 제외
- 앱 (Tauri 뷰어) 재작성 — 별도 phase. `canonical_v3.sqlite` 는 그
  백엔드로 바로 쓸 수 있는 상태다.
