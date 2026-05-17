# Report Writing 지침 (현재 활성화)

리포트 작성 / 수정 시 다음 제약을 따른다.

## 목표 톤
- Non-native graduate / upper-undergrad student
- Technical academic report tone
- Clear and direct, but with natural sentence flow
- CEFR B2-C1 어휘 (no GRE-level: delve, leverage, intricate, nuanced, multifaceted, paradigm 등 금지)

## 문장 구조
- 평균 18-25 단어 (variation 중요: 짧은 문장과 중간 길이 섞기)
- 관련 아이디어는 because / since / while / although / which 등으로 묶을 것
- 같은 주어로 시작하는 짧은 문장 3개 이상 연속 금지
  예: "I do X. I do Y. I do Z." → 합칠 것
- 리스트성 항목은 콜론(`:`)으로 본문에 자연스럽게 통합

## Voice 비율
- Active voice 는 전체 문장의 20-30 % 만
- Active voice 를 쓰는 경우 (제한적):
  - 저자의 의도 / 판단 / 선택 명시: "I argue that...", "I chose X because...", "I do not claim..."
  - 리포트 구조 안내: "Section 3 presents...", "This report focuses on..."
- 나머지는 passive 또는 무생물 주어:
  - 시스템 / 방법 / 컴포넌트가 주어: "ResNet-18 is used as the backbone", "The embeddings are L2-normalized"
  - "I use X" → "X is used"
  - "I trained the model on Y" → "The model was trained on Y"

## 금지
- 엠대시 (`—`), 세미콜론 (`;`)
- "It's not just X, it's Y" 같은 AI 식 대조
- "tapestry, navigate, foster, robust" 같은 marketing-ish 단어
- 불필요한 tricolon (3개 병렬로 묶어서 rhetorical 하게 마무리하는 패턴)
- "I do not introduce", "I do not invent" 같은 연속된 "I do not X" 패턴 → "No new X is proposed" 또는 "This work does not propose X" 로
- 한 문단에 "I" 로 시작하는 문장 2개 초과 금지

## 허용
- 1인칭 (I, we) 사용 OK (위 voice 비율 안에서)
- 기술 용어, 약어, 고유명사는 자연스럽게 사용
- 가벼운 반복 OK

---

# 프로젝트 규칙

## 현재 phase (2026-04-28 기준)

- ✅ synth_engine_v3 (코퍼스 생성, 102 K class × 200 = 20.4 M 샘플) — 종료
- ✅ train_engine_v3 (T5-light v2 학습, 38.99% top-1) — 종료, best.pt 확정
- ✅ deploy_pi Phase 1 (Keras 재구현 + Edge TPU compile) — doc/27 종료
- 🚧 deploy_pi Phase 2 (SCER 학습 + 작은 embedding head) — 다음 단계
- 🚧 deploy_pi Phase 4 (Pi/Coral 실측 latency) — 하드웨어 의존

작업 영역 우선순위: `deploy_pi/`, `train_engine_v3/{modules, scripts}/`, `doc/`. `synth_engine_v3/` 는 생성 종료, 재실행 없음.

## 환경

- Windows PyTorch 학습/추론: `.venv/Scripts/python.exe` (PyTorch 2.11+cu128, RTX 4080 Laptop GPU)
- WSL Edge TPU 변환/컴파일: `~/lab2-style-venv/bin/python` (Python 3.11.15, TF 2.15.0, onnx 1.14.1, onnx-tf 1.10.0, PyTorch 2.1.0+cpu, edgetpu_compiler 16). Phase 1 에서 확립. doc/27 §3 참고.
- Pi 추론 (실측 단계): `tflite_runtime` 또는 `ai-edge-litert` + `libedgetpu1-std`. Pi 환경 셋업은 `deploy_pi/requirements_pi.txt`.

## 자율 개발 중 명령어 작성 규칙

- cd+&& 조합 금지. 절대 경로 단일 명령으로만 실행 (Windows 권한 프롬프트 회피).
- WSL 호출 시 `wsl bash -lc "..."` 안에 절대경로 사용. Windows 경로 `d:\...` 는 WSL 안에서 `/mnt/d/...` 로 매핑됨.
- 내 수동 승인을 묻는 나쁜 예시: `cd "d:/Library/01 Admissions/01 UIUC/4-2 SP26/ECE 479/lab3" && ".venv/Scripts/python.exe" some_script.py`
- 내 승인을 묻지 않는 좋은 예시: `"d:/Library/01 Admissions/01 UIUC/4-2 SP26/ECE 479/lab3/.venv/Scripts/python.exe" "d:/Library/01 Admissions/01 UIUC/4-2 SP26/ECE 479/lab3/train_engine_v3/scripts/00_smoke.py" --out "d:/Library/01 Admissions/01 UIUC/4-2 SP26/ECE 479/lab3/train_engine_v3/out/01_smoke"`

## 자율 모드 규칙

`.claude/settings.local.json` 에서 `bypassPermissions` 활성. 멈추지 않고 계획 실행. 단 다음 규칙 필수.

### 출력 폴더 명명

- 형식: `out/NN_purpose/` (zero-pad 2자리, 단조 증가). 예: `train_engine_v3/out/15_t5_light_v2/`
- 사용자가 어느 폴더가 최신인지 한 눈에 알 수 있어야 함.
- v2 의 `out/ehanja_test` 같은 작명 금지.

### 스크립트 파일 명명

- **실행 스크립트**: `NN_name.py` 로 번호 prefix.  예: `40_port_pytorch_to_keras.py`, `43_eval_int8_accuracy.py`
- **라이브러리 모듈** (import 되는 파일): prefix 금지. 예: `keras_resnet18.py`, `model.py`, `train_loop.py`
- 이유: Python 은 `01_foo` 처럼 숫자로 시작하는 모듈명 import 불가.

### 문서 명명

- `doc/NN_TITLE.md` 형식. 번호 단조 증가. 같은 주제의 v1/v2 는 새 번호로 분리 (예: doc/26 plan → doc/27 results).
- 큰 phase 종료 시마다 결과 문서 작성. 핵심: 무엇을 검증했고, 무엇이 아직 검증 안 됐는지 명시.

### Self-discipline (bypass 모드여도 유지)

- `git commit` 은 명시 요청 시에만. 메시지에 Co-Authored-By trailer 금지 (전역 메모리).
- destructive 작업 (외부 파일 삭제, best.pt 덮어쓰기, db_src 덮어쓰기 등) 은 사전 status report.
- smoke test 우선 — 큰 배치 (1000+ 샘플) 전에 50-100 샘플로 검증.
- 같은 에러 3회 반복되면 멈추고 사용자에게 보고.
- 각 phase 완료 시 한 줄 진행 보고.

### Phase 진행 조건

큰 phase (Phase 2 SCER 등) 진입 전:
1. 계획 문서 (`doc/NN_PHASEx_PLAN.md`) 작성 후 사용자 확인
2. 영향 받는 파일 명시 (학습 코드 수정 여부 포함)
3. 검증 게이트 명시 (PASS / FAIL 기준)

작은 변경 (스크립트 추가, 문서 갱신 등) 은 자율 진행.

## 외부 피드백 반영 패턴

Codex (또는 다른 외부 리뷰어) 가 평가를 주면:
1. 동의 / 부분 동의 / 반대 항목을 분류해서 답변
2. 동의한 항목은 즉시 처리 (housekeeping → 게이트 추가 → 문서 갱신 순)
3. 검증 가능한 가설은 즉시 실험으로 결판
4. 하드웨어 의존 항목은 스크립트만 준비하고 명시적으로 미해결 표시

# userEmail
yoonguri21@gmail.com
