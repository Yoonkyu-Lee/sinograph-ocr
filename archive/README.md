# archive/

Superseded earlier iterations of the project's engines, kept for history.
The **live** pipeline lives at the repo top level (`sinograph_canonical_v3`,
`synth_engine_v3`, `train_engine_v3`, `train_engine_v4`, `deploy_pi`).

Each iteration subsumes the previous one — this is a linear v1 → v2 → v3(/v4)
progression, not parallel branches. Nothing here is needed to build or run the
current project; it is reference material only. Build outputs (`out/`,
`samples/`, …) remain git-ignored.

| Archived | Why superseded | Design docs |
|---|---|---|
| `sinograph_canonical_v1` | single-layer schema (characters + variants only) | `doc/05`, `doc/06` |
| `sinograph_canonical_v2` | expanded schema; v3 is a clean stage-build that migrates from it | `doc/11` |
| `synth_engine_v1` | 3-axis prototype, single-character test only | `doc/10` |
| `synth_engine_v2` | parallelization attempt, halted mid-run | `doc/13`, `doc/14` |
| `train_engine_v1` | early ResNet-18 baseline | `doc/12` |
| `train_engine_v2` | ONNX/TFLite export attempt, stalled | `doc/07`, `doc/12` |

The full chronological story of why each version was replaced is in the
`doc/` work-log — see `doc/INDEX.md` for the map.
