# Sinograph Dictionary — canonical_v3 기반 데스크톱 앱 (v1)

작성일: 2026-05-17. 앱: `sinograph_explorer/`.
DB: [37_CANONICAL_V3_APP_LAYER.md](37_CANONICAL_V3_APP_LAYER.md).

## 0. 배경

canonical_v3.sqlite 가 단자 사전 백엔드로 정리 완료된 뒤, 그 위에 Windows
데스크톱 사전 앱을 만들었다. 프로젝트 초창기의 Tauri 2.0 스캐폴드
(`sinograph_explorer/`, 당시 Unihan txt 파싱) 를 재사용하되 백엔드를
canonical_v3.sqlite 조회로 전면 재작성했다.

## 1. 스택

- **Tauri 2** + Vite + vanilla JS (프레임워크 없음)
- 백엔드 Rust — `rusqlite` (`bundled` feature, SQLite 를 FTS5 포함 컴파일)
- DB 는 94 MB `canonical_v3.sqlite` 를 Tauri 리소스로 번들

## 2. 백엔드 — `src-tauri/src/lib.rs`

DB 는 시작 시 (`setup` 훅) `BaseDirectory::Resource` 로 경로를 해석해
read-only 로 열고, `Mutex<Connection>` 을 Tauri managed state 로 공유한다.

command 2개:

| command | 입력 | 반환 |
|---|---|---|
| `lookup` | 한자 1글자 / `U+XXXX` | `CharacterEntry` — 구조·발음·훈음·뜻·이체자 전체 |
| `search` | 뜻·발음·훈 단어 | `Vec<SearchHit>` — FTS5 `MATCH` 결과 |

`lookup` 은 `character_summary` VIEW + `radicals` + `character_readings` +
`character_hunum` + `character_meanings` + `variant_edges` +
`variant_family` 를 codepoint 로 조회하고, `primary_ids` 문자열에서 IDC
기호를 뺀 component 한자를 navigable 한 것만 골라 함께 반환한다.

`search` 는 `fts_search` 가상테이블에 `MATCH` — query 를 `"..."` 로 감싸
FTS 문법 충돌을 피하고, 각 hit 에 한국어 뜻 첫 항목을 gloss 로 붙인다.

## 3. 프론트엔드 — `src/main.js`

- **검색바 1개** — 입력을 자동 판별: 한자 1글자 / `U+XXXX` → `lookup`,
  그 외 → `search`.
- **단자 상세** — Hero (큰 글자 / codepoint / block) + 5 패널: 구조 /
  발음 / 훈음 / 뜻 / 이체자.
- **클릭 네비게이션** — IDS 부품·부수·이체자 target·family 멤버·검색 결과
  의 모든 한자가 버튼. 클릭 → 그 글자 `lookup`. 뒤로가기 스택.
- 이체자는 `relation_category` 로 "이체 관계"(variant) 와 "관련어"(semantic)
  를 나눠 표시.

## 4. DB 번들

`tauri.conf.json` `bundle.resources` 에 `resources/canonical_v3.sqlite`
등록 → 빌드 시 설치 패키지에 포함. `src-tauri/resources/` 의 DB 는 git
비추적 (`*.sqlite` gitignore). DB 재빌드 시 수동 복사 (README 참조).

## 5. v1 범위 / 범위 밖

**v1 포함**: 직접 조회, FTS 역검색, 단자 상세 5패널, 클릭 네비게이션, 부수
한글명 표시.

**범위 밖 (다음)**:
- cytoscape 이체자 그래프 (v1 은 클릭 가능 목록)
- 부수 인덱스 브라우즈 (214 부수 → 소속 글자)
- 획순 / per-stroke 표시 — DB 측 `characters_stroke_level` 필요
- 히스토리·북마크, DB 경량화

## 6. 검증

- `cargo build` (src-tauri) — rusqlite bundled 포함 컴파일 성공.
- `npm install` + `npm run build` — 프론트엔드 번들 성공 (cytoscape 의존성
  제거).
- `npm run tauri dev` — vite + cargo 빌드 후 창 실행, setup 패닉 없음
  (DB 리소스 해석·연결 정상).
- 인터랙티브 확인 (조회·검색·네비게이션) 은 실행된 창에서 수동.

실행: `cd sinograph_explorer && npm run tauri dev`.
