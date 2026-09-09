export const api = {
    addEventListener() {},
    async fetchApi(path, init) {
        const body = init?.body ? JSON.parse(init.body) : null;
        globalThis.__calls.push({ path, body });
        const reply = globalThis.__replies[path.split("?")[0]] ?? { ok: true };
        return { ok: true, status: 200, async json() { return reply; } };
    },
};
