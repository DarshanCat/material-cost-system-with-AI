#!/usr/bin/env node
/**
 * Reports class names used in component `className` attributes that have no
 * matching selector in any stylesheet under src/.
 *
 * Usage: node scripts/check-css-classes.mjs [--json]
 * Exits 1 when undefined classes are found.
 *
 * Only static class tokens are checked: string literals inside a className
 * expression. Tokens built by interpolation (e.g. `badge-${status}`) cannot be
 * resolved statically and are skipped; list known dynamic variants in CSS instead.
 *
 * Classes that are intentional hooks with no styling of their own are listed,
 * with a reason, in scripts/css-class-allowlist.json. Allowlist entries that are
 * no longer used, or that now have a CSS rule, are reported as stale.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const srcDir = join(root, 'src');
const allowlist = JSON.parse(readFileSync(join(root, 'scripts', 'css-class-allowlist.json'), 'utf8'));

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

const files = walk(srcDir);
const cssFiles = files.filter((f) => extname(f) === '.css');
const componentFiles = files.filter((f) => ['.tsx', '.jsx'].includes(extname(f)));

/** Collect every class name that appears in a selector (or selector list). */
function cssClasses(css) {
  const classes = new Set();
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '');
  for (const match of stripped.matchAll(/([^{};]+)\{/g)) {
    const prelude = match[1].trim();
    if (prelude.startsWith('@')) continue;
    // Drop attribute selectors and string contents so `[href$=".css"]` is not read as a class.
    const selector = prelude.replace(/\[[^\]]*\]/g, '').replace(/(["'])(?:\\.|(?!\1).)*\1/g, '');
    // Escaped characters (e.g. `.py-0\.5`) are part of the class name.
    for (const cls of selector.matchAll(/\.(-?[_a-zA-Z](?:[\w-]|\\.)*)/g)) {
      classes.add(cls[1].replace(/\\(.)/g, '$1'));
    }
  }
  return classes;
}

/** Return the source text of a balanced `{ ... }` expression starting at `start`. */
function balancedBraces(src, start) {
  let depth = 0;
  for (let i = start; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}' && --depth === 0) return src.slice(start + 1, i);
  }
  return '';
}

const INTERPOLATION = '\u0000';

/**
 * Collect the string literals in a JS expression that can end up in a class list. Template
 * interpolations are replaced by a marker (so `badge-${x}` is not read as `badge-`) and scanned
 * recursively; operands of ===/!== comparisons are values being tested, not class names.
 */
function classLiterals(expr) {
  const out = [];
  let i = 0;
  while (i < expr.length) {
    const quote = expr[i];
    if (quote === "'" || quote === '"') {
      let j = i + 1;
      while (j < expr.length && expr[j] !== quote) j += expr[j] === '\\' ? 2 : 1;
      const before = expr.slice(0, i).trimEnd();
      const after = expr.slice(j + 1).trimStart();
      const compared = /[!=]==?$/.test(before) || /^[!=]==?/.test(after);
      if (!compared) out.push(expr.slice(i + 1, j));
      i = j + 1;
    } else if (quote === '`') {
      let j = i + 1;
      let text = '';
      while (j < expr.length && expr[j] !== '`') {
        if (expr[j] === '$' && expr[j + 1] === '{') {
          const inner = balancedBraces(expr, j + 1);
          out.push(...classLiterals(inner));
          text += INTERPOLATION;
          j += inner.length + 3;
        } else {
          text += expr[j++];
        }
      }
      out.push(text);
      i = j + 1;
    } else {
      i++;
    }
  }
  return out;
}

/** Extract static class tokens, with line numbers, from className attributes. */
function usedClasses(source) {
  const found = [];
  const lineOf = (index) => source.slice(0, index).split('\n').length;
  for (const match of source.matchAll(/className=/g)) {
    const at = match.index + match[0].length;
    const strings = [];
    if (source[at] === '"' || source[at] === "'") {
      const end = source.indexOf(source[at], at + 1);
      strings.push(source.slice(at + 1, end));
    } else if (source[at] === '{') {
      strings.push(...classLiterals(balancedBraces(source, at)));
    }
    for (const text of strings) {
      for (const token of text.split(/\s+/)) {
        if (!token || token.includes(INTERPOLATION)) continue;
        if (!/^-?[_a-zA-Z][\w./:-]*$/.test(token)) continue;
        found.push({ cls: token, line: lineOf(match.index) });
      }
    }
  }
  return found;
}

const defined = new Set();
for (const file of cssFiles) for (const cls of cssClasses(readFileSync(file, 'utf8'))) defined.add(cls);

/** @type {Map<string, string[]>} class -> locations */
const missing = new Map();
const used = new Set();
for (const file of componentFiles) {
  for (const { cls, line } of usedClasses(readFileSync(file, 'utf8'))) {
    used.add(cls);
    if (defined.has(cls) || Object.hasOwn(allowlist, cls)) continue;
    const loc = `${relative(root, file).replaceAll('\\', '/')}:${line}`;
    missing.set(cls, [...(missing.get(cls) ?? []), loc]);
  }
}

const sorted = [...missing.entries()].sort(([a], [b]) => a.localeCompare(b));
const stale = Object.keys(allowlist).filter((cls) => !used.has(cls) || defined.has(cls));

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ missing: Object.fromEntries(sorted), staleAllowlist: stale }, null, 2));
} else if (sorted.length === 0) {
  console.log(
    `OK: every static className in ${componentFiles.length} component files has a CSS rule ` +
      `(${defined.size} classes defined across ${cssFiles.length} stylesheets; ` +
      `${Object.keys(allowlist).length - stale.length} allowlisted hooks).`,
  );
} else {
  console.error(`Found ${sorted.length} class name(s) with no CSS rule:\n`);
  for (const [cls, locations] of sorted) {
    console.error(`  .${cls}  (${locations.length} use${locations.length === 1 ? '' : 's'})`);
    for (const loc of locations.slice(0, 5)) console.error(`      ${loc}`);
    if (locations.length > 5) console.error(`      ... and ${locations.length - 5} more`);
  }
}

if (stale.length > 0) {
  console.error(`\nStale entries in scripts/css-class-allowlist.json (unused or now styled): ${stale.join(', ')}`);
}

process.exitCode = sorted.length === 0 && stale.length === 0 ? 0 : 1;
