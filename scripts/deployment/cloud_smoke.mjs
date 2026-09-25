// Real Cognito login and authenticated synthetic workflow; no session/auth bypass.
import { chromium } from '@playwright/test';
import { randomUUID } from 'node:crypto';
const origin = process.argv[2];
const username = process.env.PLANNER_RELEASE_SMOKE_USERNAME;
const password = process.env.PLANNER_RELEASE_SMOKE_PASSWORD;
const expectedOwner = process.env.PLANNER_RELEASE_SMOKE_OWNER_ID;
const discoverOwner = process.argv[3] === "--discover-owner";
if (!origin?.startsWith('https://') || !username || !password || (!expectedOwner && !discoverOwner)) {
  throw new Error('Configure HTTPS origin and the dedicated synthetic Cognito account first.');
}
const browser = await chromium.launch({ headless: true });
let stage = "login";
try {
  const page = await browser.newPage();
  await page.goto(origin + '/api/v1/auth/login');
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await page.waitForURL(origin + '/**', { timeout: 30000 });
  const meResponse = await page.request.get(origin + '/api/v1/me');
  if (!meResponse.ok()) throw new Error('OIDC session failed');
  let me = await meResponse.json();
  if (discoverOwner) {
    console.log(JSON.stringify({ bootstrap_owner_id: me.id, oidc: 'verified', mutations: 0 }));
  } else {
    if (me.id !== expectedOwner) throw new Error('Dedicated smoke owner mismatch; no mutations sent');
    async function mutate(path, method, body) {
      const response = await page.request.fetch(origin + '/api/v1' + path, {
        method, data: body,
        headers: { 'X-CSRF-Token': me.csrf_token, 'Idempotency-Key': randomUUID() },
      });
      if (!response.ok()) throw new Error(`Synthetic command failed with status ${response.status()}`);
      return response.json();
    }
    const date = new Date(); date.setUTCDate(date.getUTCDate() + 1);
    const day = date.toISOString().slice(0, 10);
    // The isolated release account is reserved for this workflow. Retire only its prior smoke tasks.
    stage = 'commands';
    const listed = await (await page.request.get(origin + '/api/v1/tasks?state=TODO&limit=100')).json();
    for (const task of listed.items) {
      if (task.title.startsWith('R4_RELEASE_SMOKE ') && !['DONE', 'CANCELLED'].includes(task.state)) {
        const result = await mutate('/tasks/' + task.id + '/cancel', 'POST', { expected_revision: me.revision });
        me.revision = result.revision;
      }
    }
    const task = await mutate('/tasks', 'POST', {
      title: 'R4_RELEASE_SMOKE ' + randomUUID(), remaining_minutes: 30,
      deadline: { kind: 'DATE', value: day, timezone: 'UTC' }, expected_revision: me.revision,
    });
    const availability = await mutate('/availability', 'PUT', {
      windows: [{ start: day + 'T09:00:00Z', end: day + 'T12:00:00Z' }], expected_revision: task.revision,
    });
    stage = 'solve';
    const queued = await mutate('/replans', 'POST', { expected_revision: availability.revision });
    let job;
    for (let attempt = 0; attempt < 60; attempt++) {
      job = await (await page.request.get(origin + '/api/v1/jobs/' + queued.job_id)).json();
      if (job.state === 'SUCCEEDED') break;
      if (['FAILED', 'SUPERSEDED'].includes(job.state)) throw new Error('Synthetic solve failed');
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    if (job?.state !== 'SUCCEEDED') throw new Error('Synthetic solve timed out');
    const proposal = await (await page.request.get(origin + '/api/v1/proposals/' + job.proposal_id)).json();
    if (!['FEASIBLE', 'OPTIMAL'].includes(proposal.candidate.status) || proposal.candidate.constraint_report.length) {
      throw new Error('Synthetic candidate invalid');
    }
    stage = 'activation';
    await mutate('/proposals/' + job.proposal_id + '/activate', 'POST', { expected_revision: availability.revision });
    const active = await (await page.request.get(origin + '/api/v1/active-plan')).json();
    if (active.id !== job.proposal_id) throw new Error('Activation pointer mismatch');
    await page.goto(origin);
    await page.getByText('Active plan', { exact: true }).waitFor({ timeout: 15000 });
    await mutate('/tasks/' + task.id + '/cancel', 'POST', { expected_revision: availability.revision });
    console.log(JSON.stringify({ oidc: 'verified', command: 'accepted', job: 'SUCCEEDED', activation: 'verified', frontend: 'visible' }));
  }
} catch (error) {
  console.error(JSON.stringify({ state: "FAILED", stage, error_type: error.constructor.name }));
  process.exitCode = 1;
} finally {
  await browser.close();
}
