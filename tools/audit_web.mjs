/**
 * Dead-code and injection audit for the web extension.
 *
 *   node tools/audit_web.mjs
 *
 * Reports:
 *   * exports no other module imports and the module itself never uses;
 *   * interpolations of catalog or user data into innerHTML that are not run
 *     through escapeHtml — a style, family or catalog name is user-controlled
 *     text and must not be treated as markup.
 */

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..", "web");
const SKIP = new Set(["style_index.js"]);

const files = readdirSync(WEB).filter((name) => name.endsWith(".js") && !SKIP.has(name));
const sources = new Map(files.map((name) => [name, readFileSync(join(WEB, name), "utf8")]));

function stripComments(text) {
    return text.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

/* ------------------------------------------------------------- dead code */

const exports = [];
for (const [file, raw] of sources) {
    const text = stripComments(raw);
    for (const match of text.matchAll(/export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g)) {
        exports.push({ file, name: match[1] });
    }
    for (const match of text.matchAll(/export\s+const\s+([A-Za-z_$][\w$]*)/g)) {
        exports.push({ file, name: match[1] });
    }
}

const importedBy = new Map();
for (const [file, raw] of sources) {
    for (const match of stripComments(raw).matchAll(/import\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']/g)) {
        for (const part of match[1].split(",")) {
            const name = part.trim().split(/\s+as\s+/)[0].trim();
            if (!name) continue;
            if (!importedBy.has(name)) importedBy.set(name, new Set());
            importedBy.get(name).add(file);
        }
    }
}

const dead = exports.filter(({ file, name }) => {
    if (importedBy.has(name)) return false;
    const own = stripComments(sources.get(file));
    const uses = [...own.matchAll(new RegExp(`\\b${name}\\b`, "g"))].length;
    return uses <= 1;   // the declaration itself
});

/* ------------------------------------------------------- injection points */

const RISKY = [];
for (const [file, raw] of sources) {
    const text = stripComments(raw);
    const lines = text.split("\n");
    lines.forEach((line, index) => {
        if (!/innerHTML|insertAdjacentHTML|new Option\(/.test(line)) return;
        RISKY.push({ file, line: index + 1, text: line.trim() });
    });
    // template literals feeding innerHTML: look for data-ish interpolations
    for (const match of text.matchAll(/innerHTML\s*(?:=|\+=)\s*`([\s\S]*?)`/g)) {
        for (const hit of match[1].matchAll(/\$\{([^}]*)\}/g)) {
            const expression = hit[1];
            const dataish = /\b(name|family|item\.|entry\.|row\.|record\.|text|style|prompt|alias)/.test(expression);
            const escaped = /escapeHtml|encodeURIComponent|shotUrl|\?\s*"|:\s*"/.test(expression);
            if (dataish && !escaped) {
                const at = text.slice(0, text.indexOf(hit[0])).split("\n").length;
                RISKY.push({ file, line: at, text: `unescaped in innerHTML: \${${expression.trim()}}`, bad: true });
            }
        }
    }
}

console.log(`audited ${files.length} modules\n`);
console.log(`unused exports (${dead.length})`);
for (const { file, name } of dead) console.log(`  ${file}: ${name}`);
const bad = RISKY.filter((row) => row.bad);
console.log(`\nunescaped user data in markup (${bad.length})`);
for (const row of bad) console.log(`  ${row.file}:${row.line}  ${row.text}`);
process.exit(bad.length ? 1 : 0);
