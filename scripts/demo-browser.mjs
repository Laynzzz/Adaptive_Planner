/** Agent-operated synthetic walkthrough. Never targets an existing application DB. */
import { chromium, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rehearsal = process.argv.includes('--rehearsal');
const run = `${new Date().toISOString().replace(/[-:.TZ]/g, '')}${rehearsal ? '_rehearsal' : ''}`;
const database = `planner_demo_${run}`;
const out = path.join(root, '.runtime', 'demo', run);
fs.mkdirSync(out, { recursive: true });
const python = path.join(root, '.venv', 'Scripts', 'python.exe');
const databaseUrl = `postgresql+psycopg://planner:local-planner-only@127.0.0.1:25432/${database}`;
const env = { ...process.env, PLANNER_DATABASE_URL: databaseUrl };
const children = [];
const milestones = [];
let context, browser, page, started, success = false;
function command(exe, args, options = {}) {
  const result = spawnSync(exe, args, { cwd: root, env, windowsHide: true, encoding: 'utf8', ...options });
  if (result.status !== 0) throw new Error(`${path.basename(exe)} failed: ${result.stderr}`);
  return result.stdout.trim();
}
function launch(name, exe, args, cwd = root) {
  const log = fs.openSync(path.join(out, `${name}.log`), 'a');
  const child = spawn(exe, args, { cwd, env, windowsHide: true, stdio: ['ignore', log, log] });
  children.push({ name, child });
  fs.closeSync(log);
}
const json = async (url) => {
  const response = await page.request.get(`/api/v1/${url}`);
  expect(response.ok()).toBe(true);
  return response.json();
};
async function scene(title, description) {
  const seconds = Math.round((Date.now() - started) / 1000);
  milestones.push({ seconds, title, description });
  console.log(`${seconds}s: ${title}`);
  await page.evaluate(({ title, description }) => {
    const el = document.getElementById('synthetic-demo-caption');
    el.querySelector('strong').textContent = title;
    el.querySelector('p').textContent = description;
  }, { title, description });
}
async function hold(seconds) {
  if (!rehearsal) await page.waitForTimeout(Math.max(0, started + seconds * 1000 - Date.now()));
}
async function openDetails(text) {
  const summary = page.getByText(text, { exact: true });
  if (!(await summary.evaluate(el => el.parentElement.open))) await summary.click();
  await summary.scrollIntoViewIfNeeded();
}
async function closeDetails(text) {
  const summary = page.getByText(text, { exact: true });
  if (await summary.evaluate(el => el.parentElement.open)) await summary.click();
}
async function activatePlan() {
  const old = await json('active-plan');
  await page.getByRole('button', { name: 'Generate plan', exact: true }).click();
  const activate = page.getByRole('button', { name: 'Activate this plan', exact: true });
  await expect(activate).toBeEnabled({ timeout: 30000 });
  await activate.scrollIntoViewIfNeeded();
  if (!rehearsal) await page.waitForTimeout(3000);
  await activate.click();
  await expect.poll(async () => (await json('active-plan'))?.id, { timeout: 15000 }).not.toBe(old?.id);
  return json('active-plan');
}
try {
  command(python, ['-c', `import psycopg\nfrom psycopg import sql\nname=${JSON.stringify(database)}\nassert name.startswith('planner_demo_') and name.replace('_','').isalnum()\nwith psycopg.connect('postgresql://planner:local-planner-only@127.0.0.1:25432/postgres',autocommit=True) as c:\n c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))`]);
  fs.writeFileSync(path.join(out, 'migrations.log'), command(python, ['-m', 'alembic', 'upgrade', 'head']));
  launch('api', python, ['-m', 'planner.cli', 'serve']);
  launch('solver', python, ['-m', 'planner.jobs.worker']);
  launch('extraction', python, ['-m', 'planner.ai.worker']);
  launch('calendar', python, ['-m', 'planner.calendar.worker']);
  launch('vite', process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1'], path.join(root, 'apps/web'));
  fs.writeFileSync(path.join(out, 'processes.json'), JSON.stringify(children.map(({ name, child }) => ({ name, pid: child.pid })), null, 2));
  for (const url of ['http://127.0.0.1:8000/health/ready', 'http://127.0.0.1:5173']) {
    console.log(`Waiting for ${url}`);
    await expect.poll(async () => { try { return (await fetch(url)).ok; } catch { return false; } }, { timeout: 45000 }).toBe(true);
  }
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1080 }, recordVideo: { dir: out, size: { width: 1440, height: 1080 } } });
  await context.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const banner = document.createElement('aside');
      banner.id = 'synthetic-demo-caption';
      banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;background:#102f38;color:white;padding:14px 28px;min-height:110px;pointer-events:none;font:18px/1.4 system-ui;box-shadow:0 2px 12px #0005';
      banner.innerHTML = '<div style="font-size:13px;color:#a2ded3;letter-spacing:1px">AGENT-OPERATED SYNTHETIC WALKTHROUGH · LOCAL SIMULATORS · NO LIVE AI / GOOGLE</div><strong style="font-size:27px">Adaptive Planner</strong><p style="margin:4px 0">A local, isolated synthetic workspace.</p>';
      document.body.prepend(banner);
      const style = document.createElement('style');
      style.textContent = 'html{scroll-padding-top:165px}body{padding-top:150px!important}';
      document.head.append(style);
    });
  });
  page = await context.newPage();
  page.setDefaultTimeout(15000);
  started = Date.now();
  await page.goto('/');
  await scene('Start with your constraints', 'Sign in to a fresh workspace. Two tasks and one work window are enough to begin.');
  await page.getByRole('link', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('Username or email').fill('demo-b');
  await page.getByLabel('Password', { exact: true }).fill('local-demo-b-only');
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  expect((await json('tasks')).items).toHaveLength(0);
  expect(await json('active-plan')).toBeNull();
  const day = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  await scene('Initial plan · 120 minutes of work', 'Review course notes and draft a project summary. Available tomorrow, 09:00–12:00 UTC.');
  for (const title of ['Review course notes', 'Draft project summary']) {
    const form = page.getByRole('form', { name: 'Add task', exact: true });
    await form.getByLabel('Task name', { exact: true }).fill(title);
    await form.getByLabel('Remaining minutes', { exact: true }).fill('60');
    await form.getByLabel('Deadline (UTC)', { exact: true }).fill(day);
    await form.getByRole('button', { name: 'Add task', exact: true }).click();
    await expect(page.locator('.task-list > ul').getByText(title, { exact: true })).toBeVisible();
  }
  await page.getByLabel('Available from (UTC)', { exact: true }).fill(`${day}T09:00`);
  await page.getByLabel('Available until (UTC)', { exact: true }).fill(`${day}T12:00`);
  await page.getByRole('button', { name: 'Add available time' }).click();
  await expect(page.getByText('Available time saved')).toBeVisible();
  await hold(35);
  await scene('Review, then activate', 'Generating a proposal does not replace the active plan. Activation is an explicit choice.');
  const first = await activatePlan();
  expect(first.candidate.blocks.length).toBeGreaterThan(0);
  await page.screenshot({ path: path.join(out, '01-active.png') });
  await hold(70);
  await scene('Missed work · estimates stay explicit', 'Record zero minutes observed and keep 60 minutes remaining. The selected plan stays visible.');
  await openDetails('Record progress or missed work');
  await page.getByRole('combobox', { name: 'Task to update', exact: true }).selectOption({ label: 'Review course notes' });
  await page.getByLabel('New remaining estimate (minutes)', { exact: true }).fill('60');
  await page.getByRole('button', { name: 'Save progress', exact: true }).click();
  await expect(page.getByText('0 minutes observed · 60 minutes remaining', { exact: true })).toBeVisible();
  expect((await json('active-plan')).id).toBe(first.id);
  await hold(100);
  await closeDetails('Record progress or missed work');
  await scene('Protect one commitment', 'Lock the notes block, generate a new proposal and verify its time stays fixed.');
  await openDetails('Adjust blocks in your active plan');
  const block = page.locator('.active-blocks > li').filter({ has: page.getByRole('heading', { name: 'Review course notes', exact: true }) });
  await block.getByRole('button', { name: 'Lock this block', exact: true }).click();
  await expect(block.getByRole('button', { name: 'Unlock this block', exact: true })).toBeVisible();
  const notes = (await json('tasks')).items.find(t => t.title === 'Review course notes');
  const oldBlock = first.candidate.blocks.find(b => b.task_id === notes.id);
  const locked = await activatePlan();
  const kept = locked.candidate.blocks.find(b => b.task_id === notes.id);
  expect([kept.start, kept.end]).toEqual([oldBlock.start, oldBlock.end]);
  await hold(140);
  await closeDetails('Adjust blocks in your active plan');
  await scene('An impossible load stays a preview', 'Try 300 minutes for the summary inside a 180-minute window. No input or active plan changes.');
  await openDetails('Explore a change before applying it');
  await page.getByRole('combobox', { name: 'Task to explore' }).selectOption({ label: 'Draft project summary' });
  await page.getByLabel('Hypothetical remaining minutes').fill('300');
  await page.getByRole('button', { name: 'Preview changes', exact: true }).click();
  await expect(page.getByText('These changes still cannot satisfy every constraint.', { exact: true })).toBeVisible({ timeout: 30000 });
  await page.locator('.preview-result').scrollIntoViewIfNeeded();
  expect((await json('active-plan')).id).toBe(locked.id);
  expect((await json('tasks')).items.find(t => t.title === 'Draft project summary').remaining_minutes).toBe(60);
  await page.screenshot({ path: path.join(out, '02-infeasible.png') });
  await hold(180);
  await closeDetails('Explore a change before applying it');
  await scene('Extraction is a draft for review', 'Local text simulator: inspect uncertain fields before adding anything to the task list.');
  await openDetails('Describe tasks in your own words');
  await page.getByLabel('Describe your tasks', { exact: true }).fill('Review synthetic notes for 30 minutes');
  await page.getByRole('button', { name: 'Extract draft', exact: true }).click();
  const review = page.getByRole('form', { name: 'Review extracted tasks' });
  await expect(review).toBeVisible({ timeout: 30000 });
  await expect(review.getByRole('button', { name: 'Add reviewed tasks', exact: true })).toBeDisabled();
  expect((await json('tasks')).items).toHaveLength(2);
  await review.scrollIntoViewIfNeeded();
  await hold(202);
  await review.getByLabel('Use no deadline', { exact: true }).check();
  await review.getByLabel('Confirm Priority', { exact: true }).check();
  await review.getByRole('button', { name: 'Add reviewed tasks', exact: true }).click();
  await expect(page.getByText('Reviewed tasks added', { exact: true })).toBeVisible();
  expect((await json('tasks')).items).toHaveLength(3);
  await closeDetails('Describe tasks in your own words');
  await activatePlan();
  await hold(230);
  await scene('Export and connect explicitly', 'Download a portable ICS file. Calendar publication uses the dedicated local simulator.');
  await openDetails('Calendar export and connection');
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download active plan as ICS' }).click();
  await (await download).saveAs(path.join(out, 'calendar.ics'));
  expect(fs.readFileSync(path.join(out, 'calendar.ics'), 'utf8')).toContain('BEGIN:VCALENDAR');
  await page.getByLabel('This is a dedicated calendar for synthetic tasks').check();
  await page.getByRole('button', { name: 'Connect calendar', exact: true }).click();
  await expect(page.getByText('Connection: connected · Local simulator', { exact: true })).toBeVisible();
  const publish = page.getByRole('button', { name: 'Publish active plan', exact: true });
  await expect(publish).toBeEnabled({ timeout: 20000 });
  await hold(250);
  await scene('Visible failure, deliberate retry', 'TEST-ONLY INJECTION: one calendar API response returns 503. The retry uses the real durable simulator workflow.');
  await page.route('**/api/v1/calendar/publish', route => route.fulfill({ status: 503, json: { error: { code: 'DEPENDENCY_UNAVAILABLE', message: 'Calendar request temporarily unavailable.' } } }));
  await publish.click();
  await expect(page.getByText('Calendar request temporarily unavailable.', { exact: true })).toBeVisible();
  await hold(267);
  await page.unroute('**/api/v1/calendar/publish');
  await publish.click();
  await expect.poll(async () => { const s = await json('calendar/status'); return s.published_count > 0 && s.pending_count === 0 && !s.publish_pending; }, { timeout: 20000 }).toBe(true);
  await scene('Recovery confirmed', 'Publication converged. Disconnect keeps remote events by default; no live Google account was used.');
  await page.screenshot({ path: path.join(out, '03-calendar-recovered.png') });
  await page.getByText('Disconnect calendar', { exact: true }).click();
  await expect(page.getByLabel('Keep remote events after disconnecting')).toBeChecked();
  await page.getByRole('button', { name: 'Confirm disconnect', exact: true }).click();
  await expect(page.getByText('Connection: disconnected · Local simulator', { exact: true })).toBeVisible({ timeout: 20000 });
  await hold(287);
  await page.getByRole('link', { name: 'Evidence & limits', exact: true }).click();
  await scene('What this recording establishes', 'Six scripted local journeys passed. Human usability, live providers, cloud deployment and ML promotion require separate evidence.');
  await hold(300);
  success = true;
} catch (error) {
  console.error(error.message);
  fs.writeFileSync(path.join(out, 'failure.txt'), String(error.stack));
  if (page) await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true }).catch(() => {});
  process.exitCode = 1;
} finally {
  const duration = started ? (Date.now() - started) / 1000 : 0;
  await context?.close();
  await browser?.close();
  for (const { child } of children.reverse()) {
    if (child.exitCode === null) spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
  }
  const files = fs.readdirSync(out).filter(name => /\.(webm|png|ics)$/.test(name)).map(name => ({ path: `.runtime/demo/${run}/${name}`, bytes: fs.statSync(path.join(out, name)).size, sha256: createHash('sha256').update(fs.readFileSync(path.join(out, name))).digest('hex') }));
  const manifest = { version: 'synthetic-demo-v1', run, rehearsal, success, duration_seconds: duration, database, database_retained: true, processes_stopped: true, git_commit: command('git', ['rev-parse', 'HEAD']), script_sha256: createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex'), operator: 'agent-operated synthetic scripted walkthrough', live_ai: false, live_google: false, human_participants: 0, milestones, files };
  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(`DEMO_RESULT ${JSON.stringify({ success, duration, output: out })}`);
}
