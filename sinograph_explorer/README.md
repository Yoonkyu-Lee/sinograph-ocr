# Sinograph Dictionary

canonical_v3 한자 데이터베이스 위에서 동작하는 Tauri 2 데스크톱 단자(單字)
사전 앱.

> 디렉토리명 `sinograph_explorer/` 는 프로젝트 초창기 (Unihan-only 시절)
> 이름이 남은 것 — 현재 앱은 canonical_v3.sqlite 기반이다.

## 기능 (v1)

- **직접 조회** — 한자 한 글자나 `U+XXXX` 입력 → 구조 / 발음 / 훈음 / 뜻 /
  이체자 패널.
- **역검색 (FTS5)** — 뜻·발음·자훈 단어 입력 → 일치 한자 목록.
- **클릭 네비게이션** — IDS 분해 부품, 부수, 이체자, family 멤버, 검색 결과
  의 한자를 클릭하면 그 글자로 이동. 뒤로가기 지원.

## 구조

```
src/                  프론트엔드 (Vite + vanilla JS)
  main.js             검색 라우팅 · 렌더링 · 네비게이션
  styles.css
index.html
src-tauri/
  src/lib.rs          Rust 백엔드 — rusqlite 로 canonical_v3.sqlite 조회
  resources/canonical_v3.sqlite   번들 DB (git 비추적, 94 MB)
  tauri.conf.json     resources 에 DB 등록
```

백엔드 command 2개: `lookup(query)` (한 글자 전체 엔트리), `search(query,
limit)` (FTS5 역검색). DB 는 시작 시 read-only 로 열어 managed state 로 공유.

## 개발 실행

프로젝트 루트에서:

```powershell
cd .\lab3\sinograph_explorer
npm install
npm run tauri dev
```

빌드 (설치 파일):

```powershell
npm run tauri build
```

## DB 갱신

`canonical_v3.sqlite` 가 다시 빌드되면 (sinograph_canonical_v3 의 60-67
체인) 번들 DB 를 갱신한다:

```powershell
Copy-Item ..\sinograph_canonical_v3\out\canonical_v3.sqlite `
  .\src-tauri\resources\canonical_v3.sqlite -Force
```

## 다음 단계

cytoscape 이체자 그래프, 부수 인덱스 브라우즈, 획순 표시 (DB 측 stroke-level
데이터 필요), DB 경량화. 상세는 [doc/38_VIEWER_APP.md](../doc/38_VIEWER_APP.md).
