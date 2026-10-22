import React, { lazy, Suspense, useState, useRef, useEffect, useImperativeHandle, useCallback } from 'react';

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

export default function CodeEditor({ label, value, onChange, language = 'plaintext', readOnly = false, clipboardRef, defaultOpen = false, fill = false, theme = 'vs-dark', fontSize = 14, commandsRef, autoFormatInitial = false, dialect, onFormatNotice, onFormattingChange }) {
  const [ide, setIde] = useState(defaultOpen);
  const [formatting, setFormatting] = useState(false), [notice, setNotice] = useState('');
  const controls = useRef(null), textarea = useRef(null), formattingLock = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const initialFormatted = useRef(false);
  const latest = useRef(null); latest.current = { value, language, readOnly, onChange, onFormatNotice };
  const formatDocument = useCallback(async (quiet = false) => {
    if (formattingLock.current || latest.current.readOnly) return;
    const original = latest.current;
    formattingLock.current = true; setFormatting(true);
    try {
      const modules = import.meta.glob('./codeFormatting.js');
      const { formatCode } = await modules['./codeFormatting.js']();
      const formatted = await formatCode(original.value, original.language, { dialect });
      if (!mounted.current || latest.current.value !== original.value || latest.current.language !== original.language || latest.current.readOnly) return;
      if (formatted !== original.value) {
        if (controls.current) controls.current.applyFormatted(formatted);
        else latest.current.onChange(formatted);
      }
      if (!quiet) { setNotice('Code formatted'); latest.current.onFormatNotice?.('Code formatted'); }
    } catch {
      if (!quiet && mounted.current) { const message = 'Could not format this code. Check its syntax; your edits are retained.'; setNotice(message); latest.current.onFormatNotice?.(message); }
    } finally { formattingLock.current = false; if (mounted.current) setFormatting(false); }
  }, [dialect]);
  useImperativeHandle(commandsRef, () => ({ format: () => formatDocument(), undo: () => { if (controls.current) controls.current.undo(); else { textarea.current?.focus(); document.execCommand('undo'); } }, redo: () => { if (controls.current) controls.current.redo(); else { textarea.current?.focus(); document.execCommand('redo'); } }, find: () => controls.current?.find() }), [formatDocument]);
  useEffect(() => { if (!readOnly && !initialFormatted.current && autoFormatInitial && value.trim()) { initialFormatted.current = true; formatDocument(true); } }, [autoFormatInitial, language, formatDocument, value, readOnly]);
  useEffect(() => { onFormattingChange?.(formatting); }, [formatting, onFormattingChange]);
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
  const fallback = <textarea ref={textarea} aria-label={label} rows={Math.min(12, Math.max(3, value.split('\n').length))} value={value} readOnly={readOnly} onChange={e => onChange(e.target.value)}
    onCopy={copied} onPaste={pasted}
    spellCheck={false} style={{ width: '100%', height: fill ? '100%' : undefined, resize: fill ? 'none' : 'vertical', border: fill ? 0 : undefined, outlineOffset: -3, background: fill ? theme === 'vs-dark' ? '#14141c' : '#fff' : undefined, color: fill ? theme === 'vs-dark' ? '#e2e3ed' : '#262438' : undefined, boxSizing: 'border-box', fontFamily: 'Consolas, monospace', fontSize, lineHeight: 1.7, padding: fill ? '18px 24px' : 12 }} />;
  return <div role="group" aria-label={label} onKeyDownCapture={event => { if (event.altKey && event.shiftKey && event.key.toLowerCase() === 'f') { event.preventDefault(); event.stopPropagation(); formatDocument(); } }} style={{ margin: fill ? 0 : '10px 0', minWidth:0, maxWidth:'100%', height: fill ? '100%' : undefined }}>
    {!fill && <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8, flexWrap:'wrap', alignItems:'center' }}>
      <strong>{label}</strong><div><button type="button" disabled={readOnly || formatting} onClick={() => formatDocument()}>{formatting ? 'Formatting...' : 'Format code'}</button>{' '}<button type="button" onClick={() => setIde(current => !current)}>{ide ? 'Use text editor' : 'Open coding IDE'}</button></div>
    </div>}
    {!fill && notice && <small role="status">{notice}</small>}
    {ide && typeof window.Worker === 'function' ? <EditorBoundary fallback={fallback}><Suspense fallback={fallback}>
      <MonacoCodeEditor commandsRef={controls} label={label} value={value} onChange={onChange} language={language === 'nodejs' ? 'javascript' : language === 'c' ? 'cpp' : language} readOnly={readOnly} clipboardRef={clipboardRef} fill={fill} theme={theme} fontSize={fontSize} />
    </Suspense></EditorBoundary> : fallback}
  </div>;
}
