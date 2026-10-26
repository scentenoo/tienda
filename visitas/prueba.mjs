// Pruebas del recibidor, sin internet ni Cloudflare (Turso de mentira):
//
//     node visitas/prueba.mjs
import assert from "node:assert/strict";
import recibidor from "./worker.js";

const env = { TURSO_URL: "libsql://visitas-prueba.turso.io", TURSO_TOKEN: "t", ORIGEN: "https://x.github.io" };
let pedidos = [];
globalThis.fetch = async (url, opciones) => {
  pedidos.push({ url, opciones, cuerpo: JSON.parse(opciones.body) });
  return new Response(JSON.stringify({ results: [] }), { status: 200 });
};

async function mandar(cuerpo, { origen = env.ORIGEN, metodo = "POST" } = {}) {
  pedidos = [];
  const pendientes = [];
  const r = await recibidor.fetch(new Request("https://visitas.workers.dev/", {
    method: metodo, body: metodo === "POST" ? (typeof cuerpo === "string" ? cuerpo : JSON.stringify(cuerpo)) : undefined,
    headers: origen ? { Origin: origen } : {},
  }), env, { waitUntil: (p) => pendientes.push(p) });
  await Promise.all(pendientes);
  return r.status;
}

const bueno = { v: "abcd1234efgh", s: "visita0001", c: "k7m2q4xa",
                e: [{ t: "entrada" }, { t: "agregar", d: "Queso Costeño 1k", n: 1 }, { t: "raro", d: "x" }] };

// Lo bueno se guarda; lo de tipo desconocido se ignora
assert.equal(await mandar(bueno), 204);
assert.equal(pedidos.length, 1);
assert.equal(pedidos[0].url, "https://visitas-prueba.turso.io/v2/pipeline");
assert.equal(pedidos[0].opciones.headers.Authorization, "Bearer t");
const inserciones = pedidos[0].cuerpo.requests.filter((p) => p.type === "execute" && p.stmt.sql.startsWith("INSERT"));
assert.equal(inserciones.length, 2);
const args = inserciones[1].stmt.args;
assert.deepEqual(args.slice(1, 7).map((a) => a.value ?? null),
                 ["abcd1234efgh", "visita0001", "k7m2q4xa", "agregar", "Queso Costeño 1k", 1]);
assert.equal(pedidos[0].cuerpo.requests.at(-1).type, "close");

// Un código raro no se guarda como código, pero la visita sí
await mandar({ ...bueno, c: "<script>" });
assert.equal(pedidos[0].cuerpo.requests.find((p) => p.stmt?.sql.startsWith("INSERT")).stmt.args[3].type, "null");

// Textos largos se cortan
await mandar({ ...bueno, e: [{ t: "busqueda", d: "q".repeat(500), n: 0 }] });
assert.equal(pedidos[0].cuerpo.requests.find((p) => p.stmt?.sql.startsWith("INSERT")).stmt.args[5].value.length, 120);

// Lo que no cuadra no llega a Turso
assert.equal(await mandar("no es json"), 400);
assert.equal(await mandar({ v: "corto", s: "visita0001", e: [] }), 400);
assert.equal(await mandar(bueno, { origen: "https://otro.com" }), 403);
assert.equal(await mandar("x".repeat(20000)), 413);
assert.equal(await mandar(null, { metodo: "GET" }), 405);
assert.equal(pedidos.length, 0);

// Sin Origin (algunos navegadores con sendBeacon) también se acepta
assert.equal(await mandar(bueno, { origen: null }), 204);

// Si Turso falla, el catálogo igual recibe 204 (el error queda en el registro de Cloudflare)
globalThis.fetch = async () => new Response("no", { status: 500 });
const errores = [];
console.error = (...m) => errores.push(m.join(" "));
assert.equal(await mandar(bueno), 204);
assert.match(errores[0], /Turso respondió 500/);

console.log("Recibidor: todo bien");
