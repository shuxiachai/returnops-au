// Parse repository Mermaid fences. No rendering, file writes, or network requests.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
let root = path.resolve(here, '../..');
let dependencies = here;
for (let i = 2; i < process.argv.length; i += 1) {
  const option = process.argv[i];
  if (option === '--root' && process.argv[i + 1]) root = path.resolve(process.argv[++i]);
  else if (option === '--dependencies' && process.argv[i + 1]) dependencies = path.resolve(process.argv[++i]);
  else throw new Error(`Unknown or incomplete option: ${option}`);
}

const manifest = JSON.parse(fs.readFileSync(path.join(here, 'package.json'), 'utf8'));
for (const [name, version] of Object.entries(manifest.dependencies)) {
  const installed = JSON.parse(fs.readFileSync(path.join(dependencies, 'node_modules', name, 'package.json'), 'utf8'));
  if (installed.version !== version) throw new Error(`${name}: expected ${version}, found ${installed.version}; use npm ci`);
}
const requireDependency = createRequire(path.join(dependencies, 'package.json'));
const { JSDOM } = requireDependency('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.Element = dom.window.Element;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.SVGElement = dom.window.SVGElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
const { default: mermaid } = await import(pathToFileURL(requireDependency.resolve('mermaid')).href);
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });

function markdownFiles(folder) {
  if (!fs.existsSync(folder)) return [];
  return fs.readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name === 'node_modules') return [];
    const full = path.join(folder, entry.name);
    return entry.isDirectory() ? markdownFiles(full) : entry.name.endsWith('.md') ? [full] : [];
  });
}
const files = [...new Set([
  ...fs.readdirSync(root).filter((name) => name.endsWith('.md')).map((name) => path.join(root, name)),
  ...['docs', 'contracts', 'tools/model-checks'].flatMap((folder) => markdownFiles(path.join(root, folder))),
])].sort();
let diagrams = 0;
let failures = 0;
for (const file of files) {
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  let fence = null;
  let block = [];
  let startLine = 0;
  let isMermaid = false;
  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(/^\s{0,3}(`{3,}|~{3,})(.*)$/);
    if (!fence && match) {
      fence = match[1];
      isMermaid = match[2].trim() === 'mermaid';
      block = [];
      startLine = index + 1;
    } else if (fence && match && match[1][0] === fence[0] && match[1].length >= fence.length) {
      if (isMermaid) {
        try {
          const result = await mermaid.parse(block.join('\n'));
          if (!result) throw new Error('Parser returned no diagram');
          diagrams += 1;
          console.log(`PASS Mermaid parse: ${path.relative(root, file)}:${startLine} (${result.diagramType})`);
        } catch (error) {
          failures += 1;
          console.error(`FAIL Mermaid parse: ${path.relative(root, file)}:${startLine}: ${error.message}`);
        }
      }
      fence = null;
    } else if (fence) block.push(lines[index]);
  }
  if (fence) {
    failures += 1;
    console.error(`FAIL unclosed Markdown fence: ${path.relative(root, file)}:${startLine}`);
  }
}
dom.window.close();
console.log(`${files.length} Markdown files; ${diagrams} Mermaid blocks parsed; ${failures} failures.`);
console.log('Parsing only: no layout rendering, UML semantics, runtime checks or human acceptance.');
process.exitCode = failures ? 1 : 0;
