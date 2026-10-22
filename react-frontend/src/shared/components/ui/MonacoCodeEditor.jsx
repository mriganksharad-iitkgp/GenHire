import React, { useEffect, useRef, useImperativeHandle } from 'react';
import * as monaco from 'monaco-editor/editor.js';
import editorWorker from 'monaco-editor/editor/editor.worker.js?worker';
import 'monaco-editor/languages/definitions/python/register.js';
import 'monaco-editor/languages/definitions/javascript/register.js';
import 'monaco-editor/languages/definitions/java/register.js';
import 'monaco-editor/languages/definitions/cpp/register.js';
import 'monaco-editor/languages/definitions/sql/register.js';
import 'monaco-editor/features/find/register.js';
import 'monaco-editor/features/bracketMatching/register.js';
import 'monaco-editor/features/wordOperations/register.js';

window.MonacoEnvironment = { getWorker: () => new editorWorker() };

export default function MonacoCodeEditor({ label, value, onChange, language, readOnly, clipboardRef, fill = false, theme = 'vs-dark', fontSize = 14, commandsRef }) {
  const host = useRef(null);
  const editor = useRef(null);
  const onChangeRef = useRef(onChange);
  const initialRef = useRef({ value, language, readOnly, label, clipboardRef });
  onChangeRef.current = onChange;
  useImperativeHandle(commandsRef, () => ({ applyFormatted: text => { const instance = editor.current; if (!instance) return; const selection = instance.getSelection(); instance.pushUndoStop(); instance.executeEdits('format-document', [{ range: instance.getModel().getFullModelRange(), text }]); instance.pushUndoStop(); instance.setSelection(selection); }, undo: () => editor.current?.trigger('toolbar', 'undo'), redo: () => editor.current?.trigger('toolbar', 'redo'), find: () => editor.current?.getAction('actions.find')?.run() }), []);
  useEffect(() => {
    const initial = initialRef.current;
    const model = monaco.editor.createModel(initial.value, initial.language);
    const instance = monaco.editor.create(host.current, { model, theme, automaticLayout: true,
      readOnly: initial.readOnly, ariaLabel: initial.label, minimap: { enabled: false }, fontSize,
      scrollBeyondLastLine: false, tabSize: 4, wordWrap: 'on', accessibilitySupport: 'on', lineNumbersMinChars: 3, padding: { top: 12, bottom: 12 }, fontFamily: 'Consolas, "Courier New", monospace', lineHeight: 21, smoothScrolling: true });
    editor.current = instance;
    const subscription = instance.onDidChangeModelContent(() => onChangeRef.current(instance.getValue()));
    const copy = event => {
      if (!initial.clipboardRef) return;
      initial.clipboardRef.current = model.getValueInRange(instance.getSelection());
      event.clipboardData?.setData('text/plain', initial.clipboardRef.current); event.preventDefault();
    };
    const paste = event => {
      if (initial.clipboardRef && event.clipboardData?.getData('text/plain') !== initial.clipboardRef.current) {
        event.preventDefault(); event.stopPropagation(); window.dispatchEvent(new Event('oa:paste-blocked'));
      }
    };
    host.current.addEventListener('copy', copy, true); host.current.addEventListener('paste', paste, true);
    const element = host.current;
    return () => { element.removeEventListener('copy', copy, true); element.removeEventListener('paste', paste, true); subscription.dispose(); instance.dispose(); model.dispose(); editor.current = null; };
  // Initial options are captured once; updates below retain the current model.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { if (editor.current && editor.current.getValue() !== value) editor.current.setValue(value); }, [value]);
  useEffect(() => { if (editor.current) monaco.editor.setModelLanguage(editor.current.getModel(), language); }, [language]);
  useEffect(() => { editor.current?.updateOptions({ readOnly, ariaLabel: label }); }, [readOnly, label]);
  useEffect(() => { monaco.editor.setTheme(theme); }, [theme]);
  useEffect(() => { editor.current?.updateOptions({ fontSize }); }, [fontSize]);
  return <div ref={host} style={{ height: fill ? '100%' : Math.min(280, Math.max(112, (value.split('\n').length + 1) * 21)), border: fill ? 0 : '1px solid #475569', borderRadius: fill ? 0 : 8, overflow: 'hidden' }} />;
}
