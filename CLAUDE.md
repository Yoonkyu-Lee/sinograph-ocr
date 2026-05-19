# sinograph-ocr — 프로젝트 지침

CJK 한자 OCR 연구 프로젝트. 이 파일은 이 리포에서 작업할 때의 규칙이다.

## 프로젝트 상태 (2026-05-19 기준)

ML 파이프라인(코퍼스 생성 → 학습 → 배포)은 **완료**.

- 최종 모델: `train_engine_v4` 의 SCER, `deploy_pi` 로 Pi 5 + Coral 배포·검증 완료.
- 데스크톱 사전 앱은 `sinograph_explorer` 로 분리 — **별도 리포(git submodule)**.
  앱 기능 작업은 그 리포에서 한다.
- 현재 live: `sinograph_canonical_v3`, `synth_engine_v3`(동결), `train_engine_v3`
  (동결 baseline — v4 warm-start), `train_engine_v4`(최종), `deploy_pi`.
- 구버전 v1/v2 는 `archive/` 로 이동됨. 더 손대지 않음.

## 디렉터리 구조

- 최상위 = live 파이프라인만. 대체된 구버전은 `archive/` 로 (`archive/README.md`).
- `doc/` = `NN_TITLE.md` 작업 로그 (0~39). **절대 재번호·이동 안 함.**
  지도는 `doc/INDEX.md`.
- `db_mining/`, `db_src/` = 데이터 소스 (수집 스크립트 / 외부 미러).
- `sinograph_explorer/` = submodule (별도 리포). 클론 시 `--recursive`.

## 환경

- Windows PyTorch 학습/추론: `.venv/Scripts/python.exe` (PyTorch 2.11+cu128,
  RTX 4080 Laptop GPU).
- WSL Edge TPU 변환/컴파일: 별도 venv (Python 3.11, TF 2.15, edgetpu_compiler).
  셋업 절차는 `doc/27` §3.
- Pi 추론: `deploy_pi/requirements_pi.txt`.

## 명령어 작성 규칙 (자율 개발)

- `cd` + `&&` 조합 금지. 절대 경로 단일 명령으로 실행 (Windows 권한 프롬프트 회피).
- WSL 호출은 `wsl bash -lc "..."` 안에 절대경로. Windows `d:\...` 는 WSL 안에서
  `/mnt/d/...`.

## 작업 규칙

### 명명 규칙
- 출력 폴더: `out/NN_purpose/` (zero-pad 2자리, 단조 증가). 예: `out/15_t5_light_v2/`.
- 스크립트: 실행 스크립트는 `NN_name.py`, import 되는 라이브러리 모듈은 prefix 없음
  (`model.py`, `train_loop.py`). Python 은 숫자로 시작하는 모듈명을 import 못 함.
- 문서: `doc/NN_TITLE.md`, 번호 단조 증가. 큰 phase 종료 시 결과 문서를 작성하고
  `doc/INDEX.md` 를 갱신. 핵심: 무엇을 검증했고 무엇이 미검증인지 명시.

### 클린 유지 (워크스페이스가 다시 어질러지지 않도록)
- 새 버전 엔진은 `_vN` 접미사로 만든다.
- 어떤 버전이 다른 버전을 **대체(supersede)** 하면, 구버전을 `git mv` 로
  `archive/` 로 옮기고 `archive/README.md` 표를 갱신한다. 최상위에는 항상
  live 파이프라인만 보이게 유지.
- `*/out/`, `archive/*/out/` 등 생성물은 `.gitignore` 에 들어가야 한다.
- 앱 기능은 `sinograph_explorer` submodule 리포에서 작업.

### Self-discipline
- `git commit` 은 명시 요청 시에만. 커밋 메시지에 Co-Authored-By trailer 금지.
- destructive 작업 (외부 파일 삭제, best.pt 덮어쓰기 등) 은 사전 status report.
- smoke test 우선 — 큰 배치(1000+ 샘플) 전에 50-100 샘플로 검증.
- 같은 에러 3회 반복되면 멈추고 사용자에게 보고.
- 각 phase 완료 시 한 줄 진행 보고.

### Phase 진행 조건
큰 phase 진입 전: ① 계획 문서 (`doc/NN_..._PLAN.md`) 작성 후 사용자 확인
② 영향 받는 파일 명시 (학습 코드 수정 여부 포함) ③ 검증 게이트 (PASS / FAIL
기준) 명시. 작은 변경 (스크립트 추가, 문서 갱신 등) 은 자율 진행.

## 외부 피드백 반영 (Codex 등)

외부 리뷰어 평가를 받으면: ① 동의 / 부분 동의 / 반대 로 분류해 답변
② 동의 항목 즉시 처리 ③ 검증 가능한 가설은 즉시 실험으로 결판
④ 하드웨어 의존 항목은 스크립트만 준비하고 미해결로 명시.
