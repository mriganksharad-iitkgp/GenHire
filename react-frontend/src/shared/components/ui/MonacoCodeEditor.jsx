import React, { useEffect, useRef } from 'react';
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

export default function MonacoCodeEditor({ label, value, onChange, language, readOnly, clipboardRef }) {
  const host = useRef(null);
  const editor = useRef(null);
  const onChangeRef = useRef(onChange);
  const initialRef = useRef({ value, language, readOnly, label, clipboardRef });
  onChangeRef.current = onChange;
  useEffect(() => {
    const initial = initialRef.current;
    const model = monaco.editor.createModel(initial.value, initial.language);
    const instance = monaco.editor.create(host.current, { model, theme: 'vs-dark', automaticLayout: true,
      readOnly: initial.readOnly, ariaLabel: initial.label, minimap: { enabled: false }, fontSize: 14,
      scrollBeyondLastLine: false, tabSize: 2, wordWrap: 'on', accessibilitySupport: 'on' });
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
  }, []);
  useEffect(() => { if (editor.current && editor.current.getValue() !== value) editor.current.setValue(value); }, [value]);
  useEffect(() => { if (editor.current) monaco.editor.setModelLanguage(editor.current.getModel(), language); }, [language]);
  useEffect(() => { editor.current?.updateOptions({ readOnly, ariaLabel: label }); }, [readOnly, label]);
  return <div ref={host} style={{ height: 300, border: '1px solid #475569', borderRadius: 8, overflow: 'hidden' }} />;
}
