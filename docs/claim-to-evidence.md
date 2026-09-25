# Claim-to-evidence map

Claims below describe executed local evidence. They do not establish production adoption, human time savings or live-provider success. Each linked report carries commands and raw results; the final demo manifest pins its source revision and script hash.

| Bounded claim | Evidence | Limit |
| --- | --- | --- |
| Independent validation, deterministic baseline and bounded optimization enforce scheduling constraints | [Solver report](evidence/task-4-5-solver.md) | Synthetic fixtures, exact tiny oracle and property cases; capacity measurements are workload-specific |
| Authenticated workspace edits and revision fences preserve ownership and stale-write behavior | [API/UI review](evidence/task-3-7-review.md), [worker review](evidence/task-6-review.md) | Local OIDC/PostgreSQL verification |
| Calendar publication has durable retry, manual-conflict handling and owned mappings | [Calendar report](evidence/task-11-12-calendar.md) | Fake-provider fault tests; no live Google account exercised |
| Frozen v2 routing evaluation rejects learned promotion; an audited cold-policy alias correction preserves selection and all other policy records | [Evaluator and correction review](evidence/task-15-evaluator-review.md) | Observational synthetic replay; failed quality/latency gates and the v2 process-supervision limitation prevent promotion |
| Six product journeys can be completed by an automated browser | [Walkthrough and usability limits](evidence/usability.md), [script](../scripts/demo-browser.mjs) | Agent-operated synthetic execution; no human usability or adoption claim |
| A recorded technical walkthrough explains actual mechanisms and the negative routing result | [Technical recording](technical-walkthrough.md), [manifest](evidence/technical-video-manifest.json) | Agent-produced source-screen explanation; no personal interview practice claim |

Resume wording may describe implemented architecture and the exact verified scope above. Do not add an accuracy, speedup, successful cloud deployment, volunteer feedback or production claim without a corresponding executed artifact. Teaching and interview rehearsal are separate from agent-produced implementation.

## Additional measured claims

- Large synthetic task-page query-count p95 decreased from51 to2, and read p95 from46.93 to5.44ms; writep95 increased10.3% and plan-readinessp95 did not improve. [SQL report](evidence/sql-performance.md), implementation checkpoint`d145c03` (index/query implementation starts`624c04c`).
- The selected routing model remained disabled after frozen held-out evaluation and an explicit arithmetic correction. [ML report](evidence/ml-experiment.md), checkpoint`d145c03`; model/selection/raw hashes identify exact inputs.
- Windows/Linux process-tree tests reproduced escaped descendants then verified containment. [Report](evidence/process-tree-recovery.md), checkpoint`127be0a`.
- Reviewed editing and telemetry use real revision boundaries and local fault tests. [Final input review](evidence/final-input-review.md), [incident report](evidence/incident.md), checkpoint`c9d87e6`.
- Nine browser journeys pass from a fresh local checkout using real local OIDC/PostgreSQL and three workers. [Integrated release](evidence/local-release.md), application checkpoint`937ace1`.
