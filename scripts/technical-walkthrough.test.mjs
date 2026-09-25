import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { loadFrozenEvaluation } from './technical-walkthrough.mjs';

test('final capture cannot silently use pending ML evidence', () => {
  assert.throws(() => loadFrozenEvaluation(), /frozen selection and evaluation/);
});
test('evaluation must belong to the exact frozen selection', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'walkthrough-test-'));
  try {
    const selection = path.join(dir, 'selection.json');
    const evaluation = path.join(dir, 'evaluation.json');
    fs.writeFileSync(selection, JSON.stringify({ version: 'routing-selection-v1' }));
    fs.writeFileSync(evaluation, JSON.stringify({ version: 'routing-evaluation-v1', selection_sha256: 'wrong' }));
    assert.throws(() => loadFrozenEvaluation(selection, evaluation), /selection hash/);
    const report = { version: 'routing-evaluation-v1', selection_sha256: createHash('sha256').update(fs.readFileSync(selection)).digest('hex'), base_group_count: 200, decision: { promote: false, failed_gates: ['MEASUREMENT_SUPERVISION_LIMIT'] } };
    fs.writeFileSync(evaluation, JSON.stringify(report));
    assert.equal(loadFrozenEvaluation(selection, evaluation).report.decision.promote, false);
  } finally {
    assert.equal(path.dirname(path.resolve(dir)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(dir).startsWith('walkthrough-test-'));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
