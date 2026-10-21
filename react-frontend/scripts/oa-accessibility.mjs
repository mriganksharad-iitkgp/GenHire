// Structural checks on rendered DOM. Device/screen-reader/contrast acceptance
// remains manual: jsdom cannot establish layout, focus traversal or perception.
import assert from 'node:assert/strict';
export function assertNamedControls(document) {
  const named = element => {
    const refs = element.getAttribute('aria-labelledby')?.split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ');
    return (element.getAttribute('aria-label') || refs || [...(element.labels || [])].map(label => label.textContent).join(' ') ||
      (element.matches('button,a') ? element.textContent : '') || element.getAttribute('title') || '').trim();
  };
  for (const element of document.querySelectorAll('button,input:not([type=hidden]),select,textarea,a[href]')) {
    assert.ok(named(element), `Control needs an accessible name: ${element.outerHTML.slice(0, 220)}`);
  }
  const ids = [...document.querySelectorAll('[id]')].map(element => element.id);
  assert.equal(new Set(ids).size, ids.length, 'Rendered IDs must be unique.');
}
