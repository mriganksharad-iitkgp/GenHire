// All engines and WASM assets are packaged locally, including in the kiosk.
let clangReady, pythonReady;
export async function formatCode(source, language, { dialect = 'sql' } = {}) {
  if (source.length > 100000) throw new Error('Code is too large to format.');
  if (!source.trim()) return source;
  if (language === 'sql') {
    const { format } = await import('sql-formatter');
    return format(source, { language: dialect === 'sqlite' ? 'sqlite' : dialect === 'postgresql' ? 'postgresql' : 'sql', tabWidth: 4, keywordCase: 'upper', linesBetweenQueries: 1 }) + '\n';
  }
  if (language === 'python') {
    pythonReady ||= import('@wasm-fmt/ruff_fmt/vite').then(async engine => { await engine.default(); return engine; });
    const engine = await pythonReady;
    return engine.format(source, 'solution.py', { indent_style: 'space', indent_width: 4, line_width: 100 });
  }
  const extension = { cpp: 'cpp', c: 'c', java: 'java', javascript: 'js', nodejs: 'js' }[language];
  if (!extension) throw new Error('Formatting is unavailable for this language.');
  clangReady ||= import('@wasm-fmt/clang-format/vite').then(async engine => { await engine.default(); return engine; });
  const engine = await clangReady;
  return engine.format(source, `solution.${extension}`, JSON.stringify({ BasedOnStyle: 'LLVM', IndentWidth: 4, ColumnLimit: 100, AllowShortFunctionsOnASingleLine: 'None', AllowShortBlocksOnASingleLine: 'Never', SortIncludes: 'Never' }));
}
