# Synthetic walkthrough and usability limits

Protocol: one agent operates a scripted Chromium browser in a fresh isolated local workspace. Human participants: **0**. This is neither a voluntary user study nor an author-human self-test. No completion-rate, satisfaction or time-saved conclusion about people is supported.

The six scenarios cover constraint entry, explicit activation, missed work, locked replan, infeasibility interpretation, reviewed extraction and calendar retry. Assertions inspect visible UI and read-only API state. Scenario pacing is intentionally scripted for readable captions; recorded duration is not a usability performance metric.

## Executed results

Command: `node scripts/demo-browser.mjs`, 2026-09-25. Final run `20260925214127165`: **all six journeys passed**. Scripted workflow: 300.015 seconds. Saved WebM: **312.6 seconds**, 1440×1080, 15,233,429 bytes. Chromium decoded the video and inspected frames at 45, 155, 200, 258 and 293 seconds; captions, draft review, injected error and Evidence page were readable.

Video: `.runtime/demo/20260925214127165/page@dfd82a13abe3e653b3c5f6b960203136.webm`. SHA256: `281e4195d7520afaf1fc84d54c92fe0ef2f5e41e29ad9b3228c227bbc83c269b`. [Retained manifest](demo-video-manifest.json) includes milestone times, source hashes and artifact hashes. The working tree included in-progress implementation beyond baseline commit `e8c51dd23f04ab612cb97bf6f2dc27338c9c160e`; this is explicitly recorded. The local video is ignored and is not available in a clean clone unless separately supplied.

| Scenario | Observed outcome |
| --- | --- |
| Initial plan | Two tasks entered, work window saved, proposal explicitly activated |
| Missed work | Zero-minute observation retained 60 remaining; selected plan unchanged |
| Lock/replan | Locked task retained identical UTC start/end after new activation |
| Infeasible preview | Capacity-before-deadline diagnostic; real estimate and active plan unchanged |
| Reviewed extraction | Task count stayed two before confirmation and became three after acceptance |
| Calendar recovery | ICS exported; labeled API 503 visible; real simulator retry converged; keep-events disconnect completed |

Screenshots: [active plan](raw/demo-01-active.png), [infeasible preview](raw/demo-02-infeasible.png), [calendar recovery](raw/demo-03-calendar-recovered.png).

Rehearsals are separate: `20260925213855510_rehearsal` failed before browser startup because Vite bound localhost while readiness checked IPv4. The script now binds explicitly. `20260925214035518_rehearsal` passed in 15.786 seconds. Neither rehearsal is counted as a human session. Default trace sampling was 0.1; complete trace coverage is not claimed for this video.

All five launched process IDs were absent after teardown and ports 8000/5173 had no listeners at handoff. Three intentionally retained local databases are named `planner_demo_` plus the three run IDs above. They contain synthetic data only; no paid provider resources were created. Existing normal application data was not changed.

Human mistakes and subjective feedback are unavailable. The Task19 human/self-test gate remains open. The separate [technical recording](../technical-walkthrough.md) is now executed and hashed. The observed scripted success does not establish intuitive discoverability or usability for people.
