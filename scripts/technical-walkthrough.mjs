/** Local-file technical walkthrough. Final capture requires frozen ML evidence. */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const escape = text => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const fmt = value => Number.isFinite(value) ? value.toFixed(2) : 'unavailable';

export function loadFrozenEvaluation(selectionPath, evaluationPath) {
  if (!selectionPath || !evaluationPath) throw new Error('Final capture requires frozen selection and evaluation paths');
  const selectionBytes = fs.readFileSync(selectionPath);
  const evaluationBytes = fs.readFileSync(evaluationPath);
  const selection = JSON.parse(selectionBytes), report = JSON.parse(evaluationBytes);
  if (report.selection_sha256 !== sha(selectionBytes)) throw new Error('Evaluation selection hash does not match frozen selection');
  if (selection.version !== 'routing-selection-v1' || report.version !== 'routing-evaluation-v1') throw new Error('Unsupported frozen evidence version');
  if (typeof report.decision?.promote !== 'boolean' || report.base_group_count !== 200) throw new Error('Final report requires an explicit decision and 200 held-out base groups');
  return { selection, report, selection_sha256: sha(selectionBytes), evaluation_sha256: sha(evaluationBytes) };
}

function buildDeck(ml) {
  const sources = {};
  function read(file) {
    const raw = fs.readFileSync(path.join(root, file));
    sources[file] = sha(raw);
    return raw.toString('utf8');
  }
  function code(file, start, count) {
    const lines = read(file).split(/\r?\n/);
    const index = lines.findIndex(line => line.includes(start));
    if (index < 0) throw new Error(`Source anchor changed: ${file}: ${start}`);
    return `<div class="source-path">${escape(file)} · lines ${index + 1}–${index + count}</div><pre>${lines.slice(index, index + count).map((line, offset) => `<span class="line">${index + offset + 1}</span>${escape(line)}`).join('\n')}</pre>`;
  }
  const rawResult = (file, tail=8) => `<div class="source-path">${escape(file)}</div><pre class="result">${escape(read(file).trim().split(/\r?\n/).slice(-tail).join('\n'))}</pre>`;
  const sql = JSON.parse(read('docs/evidence/raw/sql-comparison-v4.json'));
  read('docs/evidence/sql-performance.md');
  const large = sql.workloads.large;
  const metrics = [
    ['Task-page p95', large.baseline.reads.latency_ms.p95, large.optimized.reads.latency_ms.p95, 'ms'],
    ['Dependency + task queries p95', large.baseline.reads.queries.p95, large.optimized.reads.queries.p95, 'queries'],
    ['Write transaction p95', large.baseline.writes.transaction_ms.p95, large.optimized.writes.transaction_ms.p95, 'ms'],
    ['Dispatcher claim p95', large.baseline.claims.latency_ms.p95, large.optimized.claims.latency_ms.p95, 'ms'],
  ];
  const table = `<table><thead><tr><th>Large storage fixture</th><th>Before</th><th>After</th></tr></thead><tbody>${metrics.map(([label,before,after,unit])=>`<tr><th>${escape(label)}</th><td>${fmt(before)} ${unit}</td><td>${fmt(after)} ${unit}</td></tr>`).join('')}</tbody></table>`;
  const evidence = [];
  const chapters = [
    {
      label: 'Solver', title: 'A fast proposal still has to pass the invariants.',
      lead: 'Greedy gives a deterministic baseline. Bounded CP-SAT can improve the same objective. Both cross an independent validation boundary.',
      mechanism: '<div class="flow"><b>Immutable snapshot</b><i>↓</i><b>Greedy → bounded CP-SAT</b><i>↓</i><b>Recompute invariants</b><i>↓</i><b>Valid proposal or explicit failure</b></div>',
      takeaway: 'A failed heuristic returns UNKNOWN. Only a valid solver result or independently validated fallback can become a proposal.',
      caption: 'Solver trade-off: bounded search may improve quality, but a quality score never substitutes for feasibility.',
      source: code('services/planner/src/planner/solver/validator.py', 'if b.owner_id != snapshot.owner_id', 13),
      proof: code('services/planner/src/planner/solver/validator.py', 'ordered = sorted(candidate.blocks', 10) + rawResult('docs/evidence/raw/task-4-green.txt', 9),
      limit: '1,000 generated examples and tiny exact comparisons are synthetic correctness evidence, not a proof of every production workload.',
    },
    {
      label: 'Concurrency', title: 'Old work cannot win after inputs or leases change.',
      lead: 'A worker computes outside the transaction. Finalization checks the persisted owner revision, calendar revision and fenced lease before storing a current proposal.',
      mechanism: '<div class="race"><div><b>Worker A</b><p>captures revision r</p><p>lease token 8</p><p class="bad">late result → rejected</p></div><div><b>Workspace / worker B</b><p>edit → revision r + 1</p><p>takeover → token 9</p><p class="good">current work may finalize</p></div></div>',
      takeaway: 'Revision rejects obsolete inputs. The fencing token rejects an expired worker even when the same durable job is retried.',
      caption: 'The two checks solve different races. Explicit activation remains a separate owner-scoped command.',
      source: code('services/planner/src/planner/jobs/handlers.py', 'if (', 17),
      proof: code('tests/integration/test_jobs.py', 'def test_stale_result_is_superseded', 12) + code('tests/integration/test_jobs.py', 'assert new.fencing_token >', 8),
      limit: 'These checks use real local PostgreSQL transactions. They do not establish hosted service availability.',
    },
    {
      label: 'Supervision', title: 'The deadline belongs to the whole process tree.',
      lead: 'Terminating a Windows venv redirector left the real interpreter alive. A descendant-marker test reproduced writes after timeout, cancellation and parent exit.',
      mechanism: '<div class="flow"><b>Supervisor</b><i>↓ owns</i><b>Windows Job Object / POSIX session</b><i>↓ contains</i><b>Redirector → interpreter → descendants</b><i>deadline / cancellation</i><b>Terminate the owned scope</b></div>',
      takeaway: 'Windows assigns the job atomically at process creation and kills it on handle close. POSIX uses a new session and group termination.',
      caption: 'Fail closed: if Windows job containment cannot be configured, the command never starts.',
      source: code('services/planner/src/planner/jobs/windows_process.py', 'jobs, handles =', 11),
      proof: rawResult('docs/evidence/raw/process-tree-red.txt', 1) + rawResult('docs/evidence/raw/process-tree-green.txt', 2) + rawResult('docs/evidence/raw/process-tree-linux.txt', 2) + '<p class="metric-note">The real descendant wrote a ready marker, then attempted a late write after cleanup. The final tests cover timeout, cancellation, parent exit, callback failure, Windows supervisor crash and containment failure.</p>',
      limit: 'POSIX process groups supervise trusted workers, not hostile daemonizing code. Abrupt supervisor death needs container/process-manager cleanup.',
    },
    {
      label: 'SQL', title: 'Fewer round trips help reads; indexes also cost writes.',
      lead: 'The final v4 study used 100,000 synthetic tasks, deterministic owners and archived jobs. Read projections preserve owner filters and keyset pagination.',
      mechanism: table,
      takeaway: 'One dependency batch replaces per-task reads. Three partial indexes target active tasks and ready/retry jobs; an unused dependency index was rejected.',
      caption: 'The comparison includes the downside: write p95 increased, and HTTP plan-readiness p95 regressed on the shared host.',
      source: code('services/planner/src/planner/db/queries.py', 'owner_id = tasks[0].owner_id', 12),
      proof: `<div class="source-path">docs/evidence/raw/sql-comparison-v4.json · raw measured values</div>${table}<p class="metric-note">Separate 10-minute HTTP studies at 2 requests/sec: ready-to-inspect p95 2.97 → 3.13 sec; SQL optimization is not a solver speedup.</p>`,
      limit: 'Shared development host, 100 reads and 20 rolled-back writes per fixture. HTTP source predates process-tree repair; it does not prove a hard descendant CPU cap.',
    },
  ];
  if (ml) {
    const report = ml.report;
    const ci = report.uncertainty?.simple_router?.mean_improvement_ci_ms;
    const policies = ['greedy','cold_cp_sat','warm_cp_sat','simple_router','learned'].filter(name=>report.policies?.[name]);
    const policyTable = `<table><thead><tr><th>Frozen policy</th><th>Mean total ms</th><th>p95 total ms</th></tr></thead><tbody>${policies.map(name=>`<tr><th>${name}</th><td>${fmt(report.policies[name].mean_total_ms)}</td><td>${fmt(report.policies[name].p95_total_ms)}</td></tr>`).join('')}</tbody></table>`;
    chapters.push({
      label:'ML result', title:report.decision.promote ? 'Promotion passed the frozen evaluation gates.' : 'The measured result does not justify promotion.',
      lead:`${report.base_group_count} held-out base groups; ${report.scenario_count} scenarios. Model, threshold and simple rule were selected before this evaluation.`,
      mechanism:policyTable,
      takeaway:report.decision.promote ? 'This is an offline promotion decision. Release pins and runtime configuration still control deployment.' : ci ? `Paired mean improvement vs simple: ${fmt(ci[0])} to ${fmt(ci[1])} ms (95% group-bootstrap interval). Negative values mean slower learned routing. Serving remains fixed.` : 'The recorded failed gates prevent promotion. Learned serving stays disabled by default.',
      caption:report.correction ? 'An audited baseline-name correction preserves the frozen model and other records. This is observational replay; serving stays fixed.' : 'Report failures and uncertainty alongside latency. Do not retune on these test outcomes.',
      source:`<div class="source-path">Frozen report · SHA256 ${ml.evaluation_sha256.slice(0,16)}…</div><pre>${escape(JSON.stringify({decision:report.decision,selected_model:ml.selection.selected_model,threshold:ml.selection.threshold,mean_quality_loss:report.promotion_metrics?.mean_quality_loss??null,invalid_accepted:report.promotion_metrics?.invalid_accepted??null,reference_completion_losses:report.promotion_metrics?.reference_completion_losses??null,worst_decile_quality_loss:report.promotion_metrics?.worst_decile_quality_loss??null},null,2))}</pre>`,
      proof:`<div class="source-path">Grouped paired uncertainty against simple_router</div><pre>${escape(JSON.stringify(report.uncertainty?.simple_router ?? {note:'No learned comparison available'},null,2))}</pre><p class="metric-note">${escape(report.timing_method)}</p>`,
      limit:report.measurement_limitations?.includes('WINDOWS_CHILD_TREE_DEADLINE_NOT_ENFORCED_V2') ? 'This v2 experiment did not enforce Windows descendant deadlines. Timings are observations; the repaired supervisor requires a new experiment.' : 'Synthetic offline policy replay; no real-user utility or fresh routed service latency claim. No deployment is enabled by this recording.',
    });
  } else {
    chapters.push({label:'ML pending',title:'ML result reserved for the frozen held-out report.',lead:'Preparation only. No test outcomes have been opened for this walkthrough.',mechanism:'<div class="pending">AWAITING FROZEN SELECTION + EVALUATION</div>',takeaway:'The final recording is blocked until hashes tie the completed report to its frozen selection.',caption:'This preparation preview cannot be labeled the final technical recording.',source:code('training/evaluate.py','selection_hash = hashlib.sha256',13),proof:'<p class="pending">No placeholder metrics. No model selection using test outcomes.</p>',limit:'Run the authorized evaluation once after selection is frozen, then supply its final report paths.'});
  }
  chapters.forEach((chapter,index)=>evidence.push({chapter:index+1,label:chapter.label,caption:chapter.caption}));
  const html=`<!doctype html><html lang="en"><meta charset="utf-8"><title>Adaptive Planner · technical walkthrough</title><style>
  *{box-sizing:border-box}body{margin:0;background:#e8edf0;color:#14343e;font:22px/1.45 system-ui}header{padding:20px 46px 16px;background:#10343e;color:white}header small{font-size:13px;letter-spacing:1.8px;color:#a7d8cf}nav{display:flex;gap:10px;margin-top:12px}button{border:1px solid #42606a;border-radius:7px;background:transparent;color:inherit;padding:9px 16px;font:16px system-ui;cursor:pointer}nav button[aria-current=true]{background:#d6f0e9;color:#10343e;border-color:#d6f0e9}main{padding:24px 46px}h1{font-size:40px;line-height:1.15;margin:0 0 14px;letter-spacing:-1px}.lead{max-width:1380px;margin:0 0 22px;font-size:23px}.grid{display:grid;grid-template-columns:42% 58%;gap:22px;height:555px}.explain,.code{background:white;border-radius:13px;padding:22px;overflow:auto}.code{background:#102b35;color:#e2efef}.source-path{font:13px/1.35 ui-monospace,monospace;color:#94c8be;margin-bottom:12px;overflow-wrap:anywhere}pre{font:16px/1.55 Consolas,monospace;margin:0 0 16px;white-space:pre-wrap;overflow-wrap:anywhere}.line{display:inline-block;color:#688a92;width:34px;user-select:none}.takeaway{font-size:20px;margin:20px 0 0;border-top:1px solid #d7e4e5;padding-top:16px}.flow{display:flex;align-items:center;flex-direction:column;text-align:center;gap:7px}.flow b{background:#edf6f3;border:1px solid #c4dfd7;padding:9px 20px;border-radius:8px;font-size:19px}.flow i{font-size:17px;font-style:normal;color:#4e7175}.race{display:grid;grid-template-columns:1fr 1fr;gap:15px;font-size:19px}.race div{background:#edf6f3;padding:15px;border-radius:8px}.bad{color:#9d382c}.good{color:#216447}table{width:100%;border-collapse:collapse;font-size:18px;text-align:left}td,th{padding:13px 8px;border-bottom:1px solid #a6c2bf;font-weight:400}thead th{font-size:15px;text-transform:uppercase}.code table{color:#e2efef}.metric-note{font-size:18px;padding:15px;background:#25424c;border-radius:7px}.pending{background:#fff2d2;color:#805419;padding:24px;border-radius:8px;font-size:23px;font-weight:600}.caption{background:#d5e9e4;padding:17px 22px;margin-top:20px;border-radius:9px;font-size:22px}.limit{font-size:16px;color:#41616a;margin:12px 0 0}.controls{display:flex;gap:12px;position:fixed;right:46px;bottom:22px;color:#153b44}.controls button{background:#fff}section[hidden]{display:none}.result{color:#b5e5b0}
  </style><header><small>AGENT-PRODUCED SOURCE WALKTHROUGH · SYNTHETIC LOCAL EVIDENCE · NO PERSONAL PRACTICE CLAIM</small><nav>${chapters.map((c,i)=>`<button data-chapter="${i}" aria-current="${i===0}">${i+1}. ${escape(c.label)}</button>`).join('')}</nav></header><main>${chapters.map((c,i)=>`<section id="chapter-${i}" ${i?'hidden':''}><h1>${escape(c.title)}</h1><p class="lead">${escape(c.lead)}</p><div class="grid"><div class="explain">${c.mechanism}<p class="takeaway">${escape(c.takeaway)}</p></div><div class="code" data-source="${i}">${c.source}</div><template id="proof-${i}">${c.proof}</template></div><p class="caption">${escape(c.caption)}</p><p class="limit">${escape(c.limit)}</p></section>`).join('')}</main><div class="controls"><button id="proof">Show executed evidence</button><button id="next">Next chapter →</button></div><script>
  let current=0;const count=${chapters.length};
  function select(n){current=n;document.querySelectorAll('section').forEach((s,i)=>s.hidden=i!==n);document.querySelectorAll('[data-chapter]').forEach((b,i)=>b.setAttribute('aria-current',String(i===n)));document.getElementById('proof').disabled=false;window.scrollTo(0,0)}
  document.querySelectorAll('[data-chapter]').forEach(b=>b.onclick=()=>select(Number(b.dataset.chapter)));
  document.getElementById('next').onclick=()=>select((current+1)%count);
  document.getElementById('proof').onclick=()=>{document.querySelector('[data-source="'+current+'"]').innerHTML=document.getElementById('proof-'+current).innerHTML;document.getElementById('proof').disabled=true};
  </script></html>`;
  return {html,sources,evidence};
}

async function main() {
  const {values}=parseArgs({options:{record:{type:'boolean'},rehearsal:{type:'boolean'},selection:{type:'string'},evaluation:{type:'string'}}});
  const final=!!values.record&&!values.rehearsal;
  const ml=values.selection||values.evaluation||final ? loadFrozenEvaluation(values.selection,values.evaluation) : null;
  const run=`technical-${new Date().toISOString().replace(/[-:.TZ]/g,'')}${values.rehearsal?'-rehearsal':''}`;
  const out=path.join(root,'.runtime','demo',run);fs.mkdirSync(out,{recursive:true});
  const deck=buildDeck(ml), htmlPath=path.join(out,'walkthrough.html');fs.writeFileSync(htmlPath,deck.html);
  const manifest={version:'technical-walkthrough-v1',run,final,ml_pending:!ml,operator:'agent-produced source-screen walkthrough',human_participants:0,source_hashes:deck.sources,script_sha256:sha(fs.readFileSync(fileURLToPath(import.meta.url))),git_commit:spawnSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).stdout.trim(),source_tree_dirty:true,chapters:deck.evidence,selection_path:values.selection,evaluation_path:values.evaluation,selection_sha256:ml?.selection_sha256,evaluation_sha256:ml?.evaluation_sha256,evaluation_correction:ml?.report.correction};
  if(values.record||values.rehearsal){
    const {chromium,expect}=await import('@playwright/test');
    const browser=await chromium.launch();
    const context=await browser.newContext({viewport:{width:1600,height:1100},recordVideo:{dir:out,size:{width:1600,height:1100}}});
    const page=await context.newPage();const start=Date.now();
    try {
      await page.goto(pathToFileURL(htmlPath).href);
      for(let i=0;i<5;i++){
        await page.locator(`[data-chapter="${i}"]`).click();
        await expect(page.locator(`#chapter-${i}`)).toBeVisible();
        console.log(`Chapter${i+1}: ${deck.evidence[i].label}`);
        await page.screenshot({path:path.join(out,`chapter-${i+1}-source.png`)});
        if(final) await page.waitForTimeout(Math.max(0,start+(i*60+32)*1000-Date.now()));
        await page.getByRole('button',{name:'Show executed evidence'}).click();
        await page.screenshot({path:path.join(out,`chapter-${i+1}-evidence.png`)});
        if(final) await page.waitForTimeout(Math.max(0,start+(i*60+46)*1000-Date.now()));
        await page.locator(`[data-source="${i}"]`).evaluate(el=>{el.scrollTop=el.scrollHeight;});
        if(final) await page.waitForTimeout(Math.max(0,start+(i+1)*60000-Date.now()));
      }
      manifest.success=true;manifest.workflow_seconds=(Date.now()-start)/1000;
    }finally{await context.close();await browser.close();}
  }
  manifest.files=fs.readdirSync(out).map(name=>({path:`.runtime/demo/${run}/${name}`,bytes:fs.statSync(path.join(out,name)).size,sha256:sha(fs.readFileSync(path.join(out,name)))}));
  fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  console.log(JSON.stringify({output:out,final,ml_pending:!ml,success:manifest.success??null}));
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) await main();
