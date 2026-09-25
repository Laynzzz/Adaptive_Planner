# Technical walkthrough recording protocol

This is an **agent-produced source-screen walkthrough**. It makes no claim that the user has personally practiced the explanation, and it is separate from the product workflow video. It uses a local HTML file and Chromium; no app server, app account, database or port 8000/5173 is needed.

The recorder reads the actual repository source and executed evidence, preserves file hashes, and generates five chapters. Each final chapter lasts 60 seconds: source/mechanism for 32 seconds, then executed evidence with a scroll to any remaining lines at 46 seconds. The total planned workflow is five minutes; the actual encoded duration must be inspected and recorded afterward.

| Chapter | Concrete teaching point | Evidence |
| --- | --- | --- |
| Solver | Greedy and bounded CP-SAT share a separately recomputed invariant boundary; heuristic failure is UNKNOWN | Actual validator source; 1,000 generated examples; [solver report](evidence/task-4-5-solver.md) |
| Concurrency | Input revision and fenced lease prevent different stale-result races | Actual finalization guards and PostgreSQL stale/takeover regression assertions |
| Supervision | Deadline/cancellation must stop descendants, including a Windows interpreter redirector | Actual job-list source and [red/green process-tree results](evidence/process-tree-recovery.md) |
| SQL | Batching and partial indexes improve reads while adding write cost | [Final v4 raw SQL](evidence/raw/sql-comparison-v4.json) and [measured report](evidence/sql-performance.md) |
| ML | Frozen selection precedes the held-out evaluation; failed promotion gates remain visible | Final selection/evaluation files supplied only after root completes the authorized frozen evaluation |

Prepare and inspect without reading any held-out results:

```powershell
node --test scripts/technical-walkthrough.test.mjs
node scripts/technical-walkthrough.mjs --rehearsal
```

After the final evaluation is supplied:

```powershell
node scripts/technical-walkthrough.mjs --record --selection <frozen-selection.json> --evaluation <test-evaluation.json>
```

Final capture rejects absent evidence, a mismatched selection hash, an unsupported artifact version, a missing promotion decision or a test report with other than 200 base groups. It does not train, evaluate, choose a model or enable deployment. A negative evaluation remains a negative result in the chapter. Policy latency comes from the report and is labeled offline replay, not a fresh serving benchmark.

The SQL chapter parses v4 metrics directly: large-page p95 46.93→5.44 ms, query p95 51→2, write p95 12.10→13.35 ms. It also shows the separate HTTP ready-to-inspect p95 regression of 2.97→3.13 seconds and the shared-host/process-supervision limitations. Earlier flawed SQL study versions are not used as final data.

## Preparation evidence

The evidence-loader regression first failed because the recorder module did not exist, then **2 tests passed**; [red](evidence/raw/technical-walkthrough-red.txt), [green](evidence/raw/technical-walkthrough-green.txt). A local Chromium rehearsal rendered all five chapters with the last explicitly labeled ML pending. Screenshots were visually inspected for readable code, numeric tables and limits. Rehearsal artifacts are ignored under `.runtime/demo/technical-20260925220408807-rehearsal`.

## Final executed recording

Status: **recorded and inspected**, 2026-09-25. Command:

```powershell
node scripts/technical-walkthrough.mjs --record --selection .runtime/training/v2/experiment/selection.json --evaluation .runtime/training/v2/experiment/test-evaluation-corrected.json
```

All five chapters completed in 300.008 scripted seconds. Encoded video duration is **313.84 seconds** (5:13.84), 1600×1100, 32,497,819 bytes. Chromium decoded the saved video and inspected frames at 45, 105, 165, 225, 255 and 285 seconds. Source excerpts, SQL measurements, failed promotion gates and uncertainty were readable.

Local video: `.runtime/demo/technical-20260925220844733/page@c60bb951412b84a1d11df9c4172801d5.webm`. SHA256: `33b8891a85a6dcf05d0b2b2b7e8807a33d06f59b962ca97a56e8455cc9afc748`. [Retained manifest](evidence/technical-video-manifest.json) pins script, source, baseline commit, selection and corrected evaluation hashes. The recording used an in-progress working tree, explicitly marked in the manifest. Video and rendered HTML remain ignored local artifacts; they are not supplied by a clean clone alone.

The ML chapter uses the audited [corrected report](evidence/raw/ml-evaluation-corrected.json), SHA256 `855cf0317aecfa068ab86a807273e3ba5cbcb3336b1f230fc0ba841e6800171f`, tied to frozen selection SHA256 `4f7b0e0396150d8f1b2d6e4590b33131979f3ade97780b5493a7707f9bb4b35f`. Review confirmed all learned/simple/greedy/warm policy records remained unchanged by the cold-baseline alias correction. The video states **do not promote**, shows the negative paired interval and failed completion/quality/latency gates, and preserves the v2 process-supervision caveat. It did not rerun evaluation or alter selection.

Retained screenshots: [SQL tradeoff](evidence/raw/technical-sql.png), [negative ML result](evidence/raw/technical-ml.png). No application ports, accounts, databases or provider services were started for this recording. Chromium closed after capture. Human usability and personal interview practice remain separate from this agent-produced explanation.
