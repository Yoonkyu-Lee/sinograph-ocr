# deploy_pi — Pi 배포 / 추론

`train_engine_v4` 의 SCER 모델을 Raspberry Pi 5 (+ Coral USB Edge TPU) 에
배포하고 추론·벤치·라이브 데모를 돌리는 코드. **배포는 완료됨** — 단계별 검증
기록은 `doc/26`~`doc/32`, 데모 런시트는 `doc/33`.

## 모델

SCER (Structure-Conditioned Embedding Recognition) — 98,169-class CJK 인식.
softmax 분류기 대신 **128-d 임베딩 + anchor DB 코사인 NN**.

- 배포 모델: `scer_int8_v20.tflite` (~11 MB INT8). Edge TPU 컴파일판은
  41/41 op 매핑.
- 보조 데이터: `scer_anchor_db_v20.npy` (98169×128 임베딩), `class_index.json`.

## 파이프라인 (PC → Pi)

```
PyTorch best.pt  (train_engine_v4/out/16_scer_v1)
   → train_engine_v4/scripts/40_port_pytorch_to_keras.py   → Keras FP32
   → train_engine_v4/scripts/41_export_keras_tflite.py     → TFLite INT8
   → edgetpu_compiler  (WSL Ubuntu)                        → Edge TPU TFLite
   → scp → Pi 5 + Coral USB
```

각 단계는 검증 게이트가 있음 (수치 parity, INT8 정확도 delta, TPU op 커버리지,
end-to-end latency) — `doc/27`, `doc/30`, `doc/32`.

## 이 폴더의 스크립트

- `infer_pi_chars.py` — 문자 PNG 추론 (단일 / 디렉터리 스윕)
- `eval_pi_scer.py` — 1000-pack 정확도 평가
- `bench_scer_pi.py` — latency 마이크로벤치
- `infer_pi_onnx.py` — ONNX 폴백 경로
- `44_make_val_pack.py` — 검증 데이터 pack 생성
- `demo/` — 라이브 데모 (3-stage), commodity OCR 어댑터, Pi Camera 캡처
- `export/` — 모델 아티팩트 (gitignored)
- `test_chars/` — 테스트 이미지

## Pi 셋업

`requirements_pi.txt` 참고 (`ai-edge-litert` 또는 `tflite_runtime`). Coral
사용 시 `sudo apt-get install libedgetpu1-std`.

## 실행 (Pi 쪽)

```bash
# 문자 PNG 추론
python3 infer_pi_chars.py \
  --tflite scer_int8_v20.tflite \
  --anchors scer_anchor_db_v20.npy \
  --class-index class_index.json \
  --image-dir test

# 라이브 데모 (3-stage)
./demo/run_stage1.sh   # CPU 벤치 — commodity OCR vs v3 vs v4
./demo/run_stage2.sh   # CPU vs Coral
./demo/run_stage3.sh   # Pi Camera 라이브 캡처
```

## 전처리 / 추론

입력은 128×128 RGB — 정사각 패딩 → bilinear resize → `/255` →
`(x-0.5)/0.5`. INT8 모델은 quantize 적용. 추론: forward → 128-d 임베딩 →
`scer_anchor_db` 코사인 NN → top-k 문자.

## 참고 문서

- `doc/24` — v3 INT8 실패 + v4 SCER 피벗 (왜 임베딩으로 갔는가)
- `doc/26`~`doc/27` — PyTorch → Keras 포트
- `doc/28`~`doc/29` — SCER 학습
- `doc/30`, `doc/32` — INT8 + Edge TPU 검증
- `doc/33` — 데모 런시트
