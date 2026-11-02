"""Exercise the Console review flow without adding a browser dependency."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


NODE_CHECK = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[1], 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = new Map();
function element(id = '') {
  return {value: '', checked: false, disabled: false, children: [], _text: '',
    set textContent(text) { this._text = String(text); this.children = []; },
    get textContent() { return this._text; },
    set innerHTML(text) { throw new Error('Review data must never be inserted as HTML: ' + text); },
    replaceChildren() { this.children = []; this._text = ''; },
    appendChild(child) { this.children.push(child); },
  };
}
function get(id) { if (!nodes.has(id)) nodes.set(id, element(id)); return nodes.get(id); }
const calls = [];
let handler;
const context = {
  document: {getElementById: get, createElement: () => element()},
  langbot: {onReady() {}, api: async (endpoint, body) => { calls.push({endpoint, body}); return handler(endpoint, body); }},
};
vm.createContext(context);
vm.runInContext(script, context);
get('scopeKey').value = 'bot:group_room';
get('userKey').value = 'bot:group_room';
get('collectionId').value = 'kb';
const untrusted = '<img src=x onerror=alert(1)>\nComplete source text';
const proposal = {proposal_id: 'p-1', summary_episode: untrusted, source_records: [{id: 'source', content: untrusted}], risk_notes: ['Verify sources']};
(async () => {
  handler = () => proposal;
  await context.previewConsolidation();
  assert.equal(get('reviewConsolidation').disabled, false);
  assert.equal(get('applyConsolidationBtn').disabled, true);
  assert.equal(get('consolidationOutput').children.filter(child => child.textContent === untrusted).length, 2);
  await context.applyConsolidation();
  assert.equal(calls.length, 1, 'Unreviewed proposal cannot run');
  get('reviewConsolidation').checked = true;
  handler = () => ({summary_episode: {id: 'summary'}});
  await context.applyConsolidation();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].endpoint, '/consolidation/run');
  assert.equal(calls[1].body.proposal_id, 'p-1');
  assert.equal(calls[1].body.user_key, 'bot:group_room');
  assert.equal(calls[1].body.model_uuid, undefined);
  assert.equal(get('reviewConsolidation').disabled, true);
  let resolve;
  handler = () => new Promise(done => { resolve = done; });
  const pending = context.previewConsolidation();
  get('collectionId').value = 'another-kb';
  context.clearConsolidation();
  resolve(proposal);
  await pending;
  assert.equal(get('reviewConsolidation').disabled, true, 'Old KB response cannot restore proposal');
  assert.equal(get('consolidationOutput').children.length, 0);
  handler = () => ({summary_episode: 'No proposal ID'});
  await context.previewConsolidation();
  get('reviewConsolidation').checked = true;
  const before = calls.length;
  await context.applyConsolidation();
  assert.equal(calls.length, before, 'Missing proposal ID cannot run');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


def test_review_flow_handles_untrusted_text_explicit_approval_and_stale_responses():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed for the Console DOM behavior check")
    root = Path(__file__).parents[2]
    html = root / "components/pages/memory_console/index.html"
    result = subprocess.run([node, "-e", NODE_CHECK, str(html)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
