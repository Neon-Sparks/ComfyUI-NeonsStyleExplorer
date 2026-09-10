/**
 * Static check for the web extension.
 *
 * `node --check` only catches syntax; it happily accepts a call to a function
 * that does not exist, which is how a missing `stripHtml` shipped and broke
 * workflow loading. This walks each module, collects everything that is
 * declared, imported or a known global, and reports any identifier that is
 * called but never defined. Regex-based on purpose (no parser available here),
 * so it checks CALLS and imports only — precise, with no false positives — and
 * does not attempt to resolve bare identifier reads.
 *
 * Known limitation: string stripping is not a lexer, so a quote character
 * inside a regex literal (/[&<>"]/) desynchronises it and produces nonsense
 * identifiers. Write such regexes with \u escapes. It also verifies that every named import actually
 * exists in the module it comes from.
 *
 *   node tools/check_web.mjs
 */

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..", "web");

const KEYWORDS = new Set([
    "const", "let", "var", "export", "import", "from", "default", "class", "extends",
    "break", "continue", "case", "throw", "finally", "delete", "void", "instanceof",
    "yield", "static", "null", "true", "false", "undefined", "arguments", "as", "of", "in",
]);

const GLOBALS = new Set([
    "window", "document", "console", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "requestAnimationFrame",
    "cancelAnimationFrame", "fetch", "alert", "confirm", "prompt", "Promise", "Array",
    "Object", "String", "Number", "Boolean", "Math", "JSON", "Set", "Map", "Date", "Error",
    "Element", "HTMLElement", "Node", "URL", "URLSearchParams", "FormData", "Blob", "FileReader", "ResizeObserver", "MutationObserver", "IntersectionObserver",
    "performance", "navigator", "Option", "Image", "CustomEvent", "Event", "parseInt",
    "parseFloat", "isNaN", "encodeURIComponent", "decodeURIComponent", "structuredClone",
    "if", "for", "while", "switch", "catch", "return", "typeof", "function", "await",
    "super", "this", "new", "else", "do", "try", "of", "in", "async", "get", "set",
    "import",   // dynamic import() is syntax, not a function to resolve
    "beforeRegisterNodeDef", "setup", "nodeCreated",
]);

function declarations(source) {
    const names = new Set();
    const add = (re, group = 1) => {
        for (const match of source.matchAll(re)) names.add(match[group]);
    };
    add(/(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g);
    add(/(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g);
    add(/(?:export\s+)?class\s+([A-Za-z_$][\w$]*)/g);
    // function parameters and destructured locals, coarse but effective
    add(/\(\s*([A-Za-z_$][\w$]*)\s*(?:,|\)\s*=>)/g);
    // every parameter of a declared function, not just the first
    for (const match of source.matchAll(/function\s*[A-Za-z_$][\w$]*\s*\(([^()]*)\)/g)) {
        for (const part of match[1].split(",")) {
            const clean = part.trim().split(/[=:]/)[0].replace(/[{}[\].]/g, "").trim();
            if (/^[A-Za-z_$][\w$]*$/.test(clean)) names.add(clean);
        }
    }
    for (const match of source.matchAll(/\(([^()]*)\)\s*=>/g)) {
        for (const part of match[1].split(",")) {
            const clean = part.trim().split(/[=:]/)[0].replace(/[{}[\].]/g, "").trim();
            if (/^[A-Za-z_$][\w$]*$/.test(clean)) names.add(clean);
        }
    }
    for (const match of source.matchAll(/(?:const|let|var)\s*\{([^}]*)\}/g)) {
        for (const part of match[1].split(",")) {
            const clean = part.trim().split(/[=:]/).pop().trim();
            if (/^[A-Za-z_$][\w$]*$/.test(clean)) names.add(clean);
        }
    }
    for (const match of source.matchAll(/for\s*\(\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g)) {
        names.add(match[1]);
    }
    return names;
}

function imports(source) {
    const found = [];
    for (const match of source.matchAll(/import\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']/g)) {
        const names = match[1]
            .split(",")
            .map((part) => part.trim().split(/\s+as\s+/).pop().trim())
            .filter(Boolean);
        found.push({ names, from: match[2] });
    }
    return found;
}

function exportsOf(source) {
    const names = new Set();
    for (const match of source.matchAll(/export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g)) names.add(match[1]);
    for (const match of source.matchAll(/export\s+(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)/g)) names.add(match[1]);
    for (const match of source.matchAll(/export\s*\{([^}]*)\}/g)) {
        for (const part of match[1].split(",")) {
            const clean = part.trim().split(/\s+as\s+/).pop().trim();
            if (clean) names.add(clean);
        }
    }
    return names;
}

/**
 * Strip comments and string bodies so identifiers inside text are not mistaken
 * for code. Template literals keep their ${...} expressions, which do contain
 * real calls.
 */
function codeOnly(source) {
    let text = source.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
    text = text.replace(/`(?:\\.|[^`\\])*`/g, (literal) => {
        const parts = [...literal.matchAll(/\$\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g)].map((m) => m[1]);
        return ` ${parts.join(" ; ")} `;
    });
    text = text.replace(/'(?:\\.|[^'\\])*'/g, "''").replace(/"(?:\\.|[^"\\])*"/g, '""');
    return text;
}

// data modules (the generated index) are not code worth walking
const DATA_FILES = new Set(["style_index.js"]);

const files = readdirSync(WEB).filter((name) => name.endsWith(".js") && !DATA_FILES.has(name));
const raw = new Map(readdirSync(WEB)
    .filter((name) => name.endsWith(".js"))
    .map((name) => [name, readFileSync(join(WEB, name), "utf8")]));
const sources = new Map(files.map((name) => [name, codeOnly(raw.get(name))]));
let problems = 0;

for (const [name, source] of sources) {
    const declared = declarations(source);
    const imported = new Set();
    for (const entry of imports(raw.get(name))) {
        for (const importedName of entry.names) imported.add(importedName);
        const target = entry.from.replace(/^\.\//, "");
        if (!raw.has(target)) continue; // external (ComfyUI) module
        const available = exportsOf(raw.get(target));
        for (const importedName of entry.names) {
            if (!available.has(importedName)) {
                console.log(`  MISSING EXPORT  ${name}: '${importedName}' is not exported by ${target}`);
                problems += 1;
            }
        }
    }

    const called = new Set();
    for (const match of source.matchAll(/(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(/g)) called.add(match[1]);
    for (const identifier of called) {
        if (GLOBALS.has(identifier) || declared.has(identifier) || imported.has(identifier)) continue;
        console.log(`  UNDEFINED CALL  ${name}: ${identifier}() is never defined or imported`);
        problems += 1;
    }

}

console.log(problems ? `web check: ${problems} problem(s)` : `web check: ${files.length} modules clean`);
process.exit(problems ? 1 : 0);
