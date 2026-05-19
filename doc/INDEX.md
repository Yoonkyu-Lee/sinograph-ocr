# doc/ — Index

40 design and work-log documents, numbered chronologically (`00`–`39`). The
set is a narrative engineering log: each major phase has a *plan* doc followed
by *results* doc(s) with explicit PASS/FAIL gates.

Documents are **never renumbered or moved** — the sequence and the
cross-references between docs are the project's history. `[archived]` marks a
doc whose subject engine now lives in `archive/` (see `archive/README.md`).

## Context & planning
- **00** Context till Lab 2 — prior-semester edge-AI lessons
- **01** Current context — Lab 3 starting point
- **02** Proposal draft — initial proposal (`02_..._v2` is the revised draft)
- **03** Idea conversation — design brainstorm
- **04** Sinograph project plan — overall architecture

## Canonical character database
- **05** Canonical DB v1 plan `[archived]`
- **06** Supplementary variant integration v1.1 `[archived]`
- **08** Stroke source coverage plan
- **09** e-hanja online reverse-engineering
- **11** Canonical DB v2 plan `[archived]`
- **17** Canonical v3 plan — consolidation into the final schema
- **21** Missing-classes audit — CJK coverage gaps
- **36** Canonical v3 completion — final build log
- **37** Canonical v3 app layer — reverse-index / lookup API

## Synthetic corpus
- **10** Stage 1 dataset generation plan
- **13** Augment / IO co-evolution plan
- **14** Generation engine optimization
- **20** Synth GPU optimization plan

## Training
- **07** Two-stage workflow
- **12** Stage 2 training plan — multi-head ResNet
- **15** Targeted fine-tune workflow
- **16** Structure-aware v3 plan
- **19** train_engine v3 plan — multi-head ResNet-18 baseline (frozen)
- **22** Train GPU optimization plan
- **23** Phase TG1 results

## Deployment — v3 INT8 failure → v4 SCER → Edge TPU
- **24** Deploy blockers & v4 plan — INT8 failure, SCER pivot
- **25** Deploy blocker report (2026-04-27) — same-day variant of doc/24
- **26** Phase 1 Keras port plan
- **27** Phase 1 results — Keras parity gates
- **28** Phase 2 SCER plan
- **29** Phase 2 results — SCER training
- **30** Phase 3/4 results — INT8 + Edge TPU
- **31** Phase 2 extension results
- **32** Phase 3/4 redo results — final verification
- **33** Demo — live run sheet

## Reports & reference
- **18** Final presentation
- **34** Report prep
- **35** Final report — academic write-up

## Desktop app — now the `sinograph_explorer` submodule (own repo)
- **38** Viewer app — Tauri integration over canonical_v3
- **39** Recognition feature — on-screen SCER recognition overlay
