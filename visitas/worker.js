// Recibidor de visitas del catálogo (ver visitas/LEEME.md).
//
// El catálogo le manda, cada pocos segundos y al cerrarse, lo que hizo el
// cliente: entró, buscó, agregó, envió… Aquí se revisa que venga bien y se
// guarda en la base de visitas de Turso, que es aparte de la de la tienda:
// este recibidor no puede ver ni tocar ventas, clientes ni deudas.
//
// Responde de una (204) y guarda después, para que el catálogo nunca espere.
//
// Variables:
//   TURSO_URL     la base de visitas, libsql://visitas-<usuario>.turso.io (secreto)
//   TURSO_TOKEN   token de esa base (secreto)
//   ORIGEN        de dónde se aceptan avisos (en wrangler.toml)

const TIPOS = new Set(["entrada", "categoria", "busqueda", "agregar", "quitar",
                       "vaciar", "ver_pedido", "enviar", "escribir", "salida"]);
const ID = /^[a-z0-9]{8,32}$/;
const CODIGO = /^[a-z0-9]{4,16}$/;
const MAXIMO_CUERPO = 16384, MAXIMO_EVENTOS = 50, LARGO_DATO = 120;

const CREAR = [
  `CREATE TABLE IF NOT EXISTS eventos (
     id INTEGER PRIMARY KEY,
     momento TEXT NOT NULL,      -- UTC, 2026-10-26T23:05:01.123Z
     visitante TEXT NOT NULL,    -- al azar, guardado en el teléfono: la misma persona otro día
     visita TEXT NOT NULL,       -- al azar, cada vez que abre la página
     codigo TEXT,                -- el del enlace (?c=…): de qué cliente es; NULL si no vino con uno
     tipo TEXT NOT NULL,
     dato TEXT,                  -- el producto, lo buscado, la categoría…
     valor REAL,                 -- la cantidad, los resultados, el total, los segundos…
     pais TEXT)`,
  "CREATE INDEX IF NOT EXISTS eventos_momento ON eventos (momento)",
];
const INSERTAR = "INSERT INTO eventos (momento, visitante, visita, codigo, tipo, dato, valor, pais) " +
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)";

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") return respuesta(env, 204);
    if (request.method !== "POST") return respuesta(env, 405);
    const origen = request.headers.get("Origin");
    if (env.ORIGEN && origen && origen !== env.ORIGEN) return respuesta(env, 403);

    const texto = await request.text();
    if (texto.length > MAXIMO_CUERPO) return respuesta(env, 413);
    let filas;
    try {
      filas = leer(JSON.parse(texto), new Date(), request.cf && request.cf.country);
    } catch (e) {
      return respuesta(env, 400);
    }
    if (filas.length) ctx.waitUntil(guardar(env, filas).catch((e) => console.error("No se guardó:", e.message)));
    return respuesta(env, 204);
  },
};

function respuesta(env, estado) {
  return new Response(null, { status: estado, headers: {
    "Access-Control-Allow-Origin": env.ORIGEN || "*",
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Content-Type",
  } });
}

// {v, s, c, e: [{t, d, n}]} → filas para la tabla. Lo que no cuadre, error.
function leer(datos, ahora, pais) {
  if (!datos || !ID.test(datos.v) || !ID.test(datos.s) || !Array.isArray(datos.e)) throw new Error("forma");
  const codigo = typeof datos.c === "string" && CODIGO.test(datos.c) ? datos.c : null;
  const momento = ahora.toISOString();
  return datos.e.slice(0, MAXIMO_EVENTOS).filter((e) => e && TIPOS.has(e.t)).map((e) => [
    momento, datos.v, datos.s, codigo, e.t,
    typeof e.d === "string" && e.d ? e.d.slice(0, LARGO_DATO) : null,
    typeof e.n === "number" && Number.isFinite(e.n) ? e.n : null,
    typeof pais === "string" ? pais.slice(0, 2) : null,
  ]);
}

function valor(v) {
  if (v === null) return { type: "null" };
  if (typeof v === "number") return { type: "float", value: v };
  return { type: "text", value: v };
}

// Todo en una sola ida a Turso (API HTTP: /v2/pipeline)
async function guardar(env, filas) {
  const pasos = CREAR.map((sql) => ({ type: "execute", stmt: { sql } }));
  for (const fila of filas) pasos.push({ type: "execute", stmt: { sql: INSERTAR, args: fila.map(valor) } });
  pasos.push({ type: "close" });
  const url = env.TURSO_URL.replace(/^libsql:\/\//, "https://").replace(/\/$/, "") + "/v2/pipeline";
  const r = await fetch(url, {
    method: "POST",
    headers: { Authorization: "Bearer " + env.TURSO_TOKEN, "Content-Type": "application/json" },
    body: JSON.stringify({ requests: pasos }),
  });
  if (!r.ok) throw new Error("Turso respondió " + r.status);
  const cuerpo = await r.json();
  const fallo = (cuerpo.results || []).find((x) => x.type === "error");
  if (fallo) throw new Error(fallo.error && fallo.error.message);
}
