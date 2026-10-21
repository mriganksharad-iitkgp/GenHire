import React, { lazy, Suspense, useState } from 'react';

// Vite bundles the editor/workers locally. Opening a private reference solution
// never downloads an editor from a CDN or sends source to an external service.
const MonacoCodeEditor = lazy(() => {
  const modules = import.meta.glob('./MonacoCodeEditor.jsx');
  return modules['./MonacoCodeEditor.jsx']();
});

class EditorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

export default function CodeEditor({ label, value, onChange, language = 'plaintext', readOnly = false, clipboardRef }) {
  const [ide, setIde] = useState(false);
  const copied = event => {
    if (!clipboardRef) return;
    clipboardRef.current = value.slice(event.target.selectionStart, event.target.selectionEnd);
    event.clipboardData?.setData('text/plain', clipboardRef.current); event.preventDefault();
  };
  const pasted = event => {
    if (clipboardRef && event.clipboardData?.getData('text/plain') !== clipboardRef.current) {
      event.preventDefault(); event.stopPropagation(); window.dispatchEvent(new Event('oa:paste-blocked'));
    }
  };
  const fallback = <textarea aria-label={label} rows={8} value={value} readOnly={readOnly} onChange={e => onChange(e.target.value)}
    onCopy={copied} onPaste={pasted}
    spellCheck={false} style={{ width: '100%', boxSizing: 'border-box', fontFamily: 'Consolas, monospace', padding: 12 }} />;
  return <div role="group" aria-label={label} style={{ margin: '16px 0', minWidth:0, maxWidth:'100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8, flexWrap:'wrap', alignItems:'center' }}>
      <strong>{label}</strong><button type="button" onClick={() => setIde(current => !current)}>{ide ? 'Use text editor' : 'Open coding IDE'}</button>
    </div>
    {ide && typeof window.Worker === 'function' ? <EditorBoundary fallback={fallback}><Suspense fallback={fallback}>
      <MonacoCodeEditor label={label} value={value} onChange={onChange} language={language} readOnly={readOnly} clipboardRef={clipboardRef} />
    </Suspense></EditorBoundary> : fallback}
  </div>;
}
