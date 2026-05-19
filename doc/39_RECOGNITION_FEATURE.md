# doc/39 — 화면 한자 인식 기능 (SCER 모델 앱 통합)

## 개요

lab3 캡스톤에서 학습한 **SCER 한자 인식 모델**(ResNet-18 + 128-d embedding,
이미지→한자 유추)을 `sinograph_explorer` 데스크톱 사전 앱에 통합했다. 사용자가
화면 어디서나 한자를 인식해 바로 사전 검색할 수 있다.

동작: 전역 단축키(Ctrl+Shift+H) 또는 앱 버튼 → 투명 오버레이 → 커서를
따라다니는 "유효범위" 사각형 → 멈추면(디바운스 300ms) 그 영역을 캡처해 실시간
인식 → 사각형 옆에 후보 한자 → **클릭하여 사각형 고정** → 후보 클릭 → 메인 창에
사전 항목. Esc 취소.

## 아키텍처

- **추론 = Rust 네이티브** `tract-onnx` (외부 런타임·Python 불필요).
  SCER 체크포인트를 ONNX 로 export 후 `tract` 로 실행.
- **코사인 NN** = `ndarray` matmul. 128-d embedding → anchor DB(98169×128)와
  코사인 유사도 → top-K. `select_nth_unstable_by` 로 부분 정렬.
- **화면 캡처** = `xcap` (커서가 있는 모니터 캡처 → 사각형 영역 crop).
- **오버레이 캡처 제외** = `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`
  (`windows` crate). 실시간 캡처 루프가 오버레이 자신을 찍지 않게 한다.
- **전역 단축키** = `tauri-plugin-global-shortcut`, Rust 핸들러로만 처리.
- 좌표 계산은 전부 Rust 에서 physical px 로. JS 는 사각형 그리기와 디바운스만.

## 마일스톤 & 게이트 결과

| M | 내용 | 게이트 결과 |
|---|---|---|
| M0 | SCER → ONNX export (`52_export_scer_onnx.py`) | PASS — top-1 18/20(90%), top-5 20/20, ONNX↔torch 차이 3.5e-7 |
| M1 | Rust `tract` 추론 경로 (`recognize.rs`) | PASS — top-1 18/20, Python ONNX 결과와 완전 일치 |
| M2 | Vite 멀티페이지 + 오버레이 창 | PASS — 투명 오버레이가 커서 모니터(보조 모니터 포함)에 정상 |
| M3 | 오버레이 UI (커서 추종 사각형 + 후보 패널) | PASS — 사각형 추종, 휠 크기 조절 |
| M4 | 좌표/DPI 처리 (physical px crop) | PASS — 캡처 영역이 사각형과 일치 |
| M5 | 실시간 인식 루프 (디바운스 300ms) | PASS — 끊김 없이 후보 갱신 |
| M6 | 전역 단축키 Ctrl+Shift+H | PASS — 다른 앱 위에서도 오버레이 실행 |
| M7 | 캡처 제외 + 후보 선택 핸드오프 | PASS — 후보 클릭 → 메인 창 사전 항목 |

체크포인트-앵커 짝: 디스크의 `16_scer_v1/best.pt` 는 epoch-20 가중치
(emb/top1 0.952) → `scer_anchor_db_v20.npy` 와 짝지음.

## 영향 받은 파일

신규: `train_engine_v4/scripts/52_export_scer_onnx.py`,
`sinograph_explorer/{vite.config.js, overlay.html, src/overlay.js,
src/overlay.css}`, `src-tauri/{src/recognize.rs, examples/m1_gate.rs,
capabilities/overlay.json, resources/(scer_v4.onnx, scer_anchor_db_v20.npy,
class_index.json)}`.

수정: `src-tauri/{Cargo.toml, tauri.conf.json, src/lib.rs}`,
`src/{main.js, styles.css}`, `index.html`.

학습 코드(`train_engine_v4/modules`)는 수정 없음 — export 스크립트만 추가.

## 검증됨 / 미검증

검증됨:
- M0–M7 게이트 전부 통과 (위 표).
- 실측: IIDX 앨범 자켓 사진의 한자를 79% 유사도로 top-1 인식 — 렌더 글리프
  외 실사 이미지에서도 동작.
- 보조 모니터(음수 좌표)에서 오버레이·캡처 정상.

미검증 / 남은 일:
- `npm run tauri build` 릴리스 설치 파일 (리소스 +~100MB 번들). dev 모드는
  완전 동작 확인.
- 다양한 배율(125%/150%/175%) 전수 검증은 안 함 — 좌표 로직은 scale_factor
  기반이라 이론상 무관.
- 넓은 실사 이미지셋 정확도 통계는 lab3 평가(emb/top1 0.95)로 갈음.

## 사용법

1. 앱 검색바의 "화면 한자 인식" 버튼 또는 **Ctrl+Shift+H**.
2. 초록 사각형을 한자 위에 놓는다 (휠로 크기 조절). 후보가 실시간으로 뜬다.
3. **클릭** → 사각형 고정(테두리 황색), 후보 패널 정지.
4. 후보 한자 클릭 → 오버레이 닫히고 메인 창에 사전 항목.
5. 빈 곳 클릭 = 다시 조준, Esc = 취소.

## 향후

- 릴리스 빌드 + 설치 파일 검증.
- 인식 정확도가 낮을 때 신뢰도 표시/경고.
- crop 전처리에 contour-tighten 추가 (실사 이미지 추가 강건성).
