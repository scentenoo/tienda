"""Informe de pendientes para el celular: un solo archivo HTML, sin nada
externo, que se manda por WhatsApp y se abre en el navegador del teléfono.

A diferencia del PDF, quien lo recibe puede ordenar tocando las columnas,
buscar por nombre y filtrar por días de mora, sin que haya que mandarle un
documento por cada orden.
"""
import json
from datetime import datetime
from html import escape
import unicodedata
from pathlib import Path

from utils.pdf import CARPETA


def html_pendientes(filas, telefonos=None, enlaces=None, arriba="") -> str:
    """La página completa. filas: las de conciliacion.deudores();
    telefonos: {nombre: teléfono}; enlaces: {nombre: url} para que el nombre
    lleve a la ficha del cliente (la página del celular); arriba: HTML que va
    antes del título (el enlace para volver)."""
    telefonos, enlaces = telefonos or {}, enlaces or {}
    datos = [{"n": nombre, "d": round(deuda), "f": desde or "", "x": dias,
              "t": "".join(c for c in (telefonos.get(nombre) or "") if c.isdigit() or c == "+"),
              "u": enlaces.get(nombre, "")}
             for nombre, deuda, desde, dias in filas]
    # "</" dentro del JSON cerraría la etiqueta <script> antes de tiempo
    json_datos = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    total = sum(r["d"] for r in datos)
    return (PLANTILLA.replace("__ARRIBA__", arriba)
            .replace("__CSS_SIN_JS__", _css_sin_js()).replace("__SIN_JS__", _version_sin_js(datos))
            .replace("__KTOTAL__", _pesos(total)).replace("__KCLIENTES__", str(len(datos)))
            .replace("__DATOS__", json_datos).replace("__GENERADO__", generado))


def _pesos(v):
    return "$" + f"{round(v):,.0f}".replace(",", ".")


def _nivel(dias):
    dias = dias or 0
    return "alta" if dias >= 60 else "media" if dias >= 30 else "baja" if dias >= 15 else ""


# ── Versión sin JavaScript ───────────────────────────────────────────────────
# El visor de archivos de WhatsApp y de Android no ejecuta JavaScript. Para que
# igual se pueda ordenar tocando las columnas y filtrar por días, el archivo
# trae la tabla ya ordenada de las 6 formas posibles y unos botones de radio
# ocultos: tocar un título marca otro botón y el CSS muestra la tabla que toca.
# Buscar por nombre sí necesita JavaScript (en Chrome funciona todo).
FILTROS = (0, 15, 30, 60)
ORDENES = [("d", True), ("d", False), ("n", False), ("n", True), ("x", True), ("x", False)]
TITULOS = (("n", "Cliente", ""), ("d", "Deuda", "num"), ("x", "Días", "num"))


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower()


def _fila_html(r, clases=""):
    nombre = (f'<a class="nombre" href="{escape(r["u"])}">{escape(r["n"])}</a>' if r["u"]
              else f'<span class="nombre">{escape(r["n"])}</span>')
    tel = f'<a class="tel" href="tel:{escape(r["t"])}" aria-label="Llamar">📞</a>' if r["t"] else ""
    desde = f'<div class="desde">debe desde el {escape(r["f"])}</div>' if r["f"] else ""
    return (f'<tr class="{(_nivel(r["x"]) + " " + clases).strip()}"><td>{nombre}{tel}{desde}</td>'
            f'<td class="num">{_pesos(r["d"])}</td>'
            f'<td class="num dias">{"" if r["x"] is None else r["x"]}</td></tr>')


def _version_sin_js(datos):
    def clave(col):
        if col == "n":
            return lambda r: _sin_tildes(r["n"])
        return lambda r: -1 if r[col] is None else r[col]

    def marcas(r):
        return " ".join(f"m{f}" for f in FILTROS[1:] if (r["x"] or 0) >= f)

    html = []
    for col, desc in ORDENES:
        marcado = " checked" if (col, desc) == ("d", True) else ""
        html.append(f'<input type="radio" name="orden" id="o-{col}-{"desc" if desc else "asc"}"{marcado}>')
    for f in FILTROS:
        html.append(f'<input type="radio" name="filtro" id="f{f}"{" checked" if f == 0 else ""}>')
    html.append('<div class="chips">' + "".join(
        f'<label for="f{f}">{"Todos" if f == 0 else f"{f}+ días"}</label>' for f in FILTROS) + "</div>")

    pies = []
    for f in FILTROS:
        dentro = [r for r in datos if (r["x"] or 0) >= f]
        pies.append(f'<tr class="psj f{f}"><td>Total ({len(dentro)})</td>'
                    f'<td class="num">{_pesos(sum(r["d"] for r in dentro))}</td><td></td></tr>')
        if not dentro:
            pies.append(f'<tr class="vsj f{f}"><td colspan="3" class="vacio">'
                        f'No hay clientes con ese filtro</td></tr>')

    html.append('<div class="tablas">')
    for col, desc in ORDENES:
        filas = sorted(datos, key=clave(col), reverse=desc)
        cabeza = []
        for c, titulo, clase in TITULOS:
            # Tocar la columna actual invierte el orden; otra columna empieza
            # en su orden natural (nombres A→Z, números de mayor a menor)
            siguiente = (not desc) if c == col else (c != "n")
            flecha = (" ▼" if desc else " ▲") if c == col else ""
            cabeza.append(f'<th class="{clase}"><label for="o-{c}-{"desc" if siguiente else "asc"}">'
                          f'{titulo}{flecha}</label></th>')
        html.append(f'<table class="tsj t-{col}-{"desc" if desc else "asc"}">'
                    f'<thead><tr>{"".join(cabeza)}</tr></thead><tbody>'
                    + "".join(_fila_html(r, "fsj " + marcas(r)) for r in filas)
                    + f'</tbody><tfoot>{"".join(pies)}</tfoot></table>')
    html.append("</div>")
    return "".join(html)


def _css_sin_js():
    reglas = ["#sinjs > input { display: none; }", ".tsj, .psj, .vsj { display: none; }",
              ".tsj th label { display: block; cursor: pointer; }",
              ".chips label { flex: none; border-radius: 999px; padding: 8px 14px; font-size: .9rem;"
              " background: var(--chip); color: var(--texto); cursor: pointer; }"]
    for col, desc in ORDENES:
        o = f'{col}-{"desc" if desc else "asc"}'
        reglas.append(f"#o-{o}:checked ~ .tablas .t-{o} {{ display: table; }}")
    for f in FILTROS:
        reglas.append(f"#f{f}:checked ~ .tablas .psj.f{f}, #f{f}:checked ~ .tablas .vsj.f{f}"
                      f" {{ display: table-row; }}")
        reglas.append(f"#f{f}:checked ~ .chips label[for=f{f}] {{ background: var(--acento);"
                      f" color: var(--tarjeta); font-weight: 600; }}")
        if f:
            reglas.append(f"#f{f}:checked ~ .tablas tr.fsj:not(.m{f}) {{ display: none; }}")
    return "\n".join(reglas)


def exportar_pendientes_html(filas, telefonos=None) -> Path:
    """El archivo para mandar por WhatsApp, en Documentos\\Informes."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA / f"pendientes_{datetime.now():%Y-%m-%d_%H-%M}.html"
    ruta.write_text(html_pendientes(filas, telefonos), encoding="utf-8")
    return ruta


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pendientes por cobrar</title>
<style>
:root {
  --fondo: #f4f5f7; --tarjeta: #ffffff; --texto: #1f2933; --suave: #6b7580;
  --borde: #e2e5e9; --acento: #2c3e50; --chip: #e9ecef;
  --baja: #fff3cd; --baja-t: #7a5a0c; --media: #ffe0b2; --media-t: #8a4518;
  --alta: #f8d7da; --alta-t: #a3242f;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fondo: #14171a; --tarjeta: #1d2126; --texto: #e6e8ea; --suave: #9aa3ad;
    --borde: #2e343b; --acento: #8fb3d9; --chip: #2a3036;
    --baja: #3a3113; --baja-t: #f1d27a; --media: #3d2a17; --media-t: #f5b27a;
    --alta: #43201f; --alta-t: #f19a9f;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); color: var(--texto);
  font: 16px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 640px; margin: 0 auto; padding: 16px; }
h1 { font-size: 1.35rem; margin: 0 0 2px; }
.gen { color: var(--suave); font-size: .85rem; margin-bottom: 14px; }
.resumen { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.kpi { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px; padding: 10px 12px; }
.kpi b { display: block; font-size: 1.3rem; font-variant-numeric: tabular-nums; }
.kpi span { color: var(--suave); font-size: .8rem; }
input[type=search] { width: 100%; font-size: 16px; padding: 11px 14px; border-radius: 10px;
  border: 1px solid var(--borde); background: var(--tarjeta); color: var(--texto); }
.chips { display: flex; gap: 8px; overflow-x: auto; padding: 10px 0 12px; }
.chips button { flex: none; border: 0; border-radius: 999px; padding: 8px 14px; font-size: .9rem;
  background: var(--chip); color: var(--texto); }
.chips button.on { background: var(--acento); color: var(--tarjeta); font-weight: 600; }
table { width: 100%; border-collapse: collapse; background: var(--tarjeta);
  border: 1px solid var(--borde); border-radius: 12px; overflow: hidden; }
th { position: sticky; top: 0; background: var(--acento); color: var(--tarjeta); font-size: .9rem;
  text-align: left; padding: 12px 10px; user-select: none; cursor: pointer; white-space: nowrap; }
th.num, td.num { text-align: right; }
td { padding: 10px; border-top: 1px solid var(--borde); vertical-align: middle; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.nombre { font-weight: 600; }
a.nombre { color: inherit; text-decoration: underline; text-underline-offset: 3px; }
a.volver { display: inline-block; margin-bottom: 10px; color: var(--acento); text-decoration: none; font-weight: 600; }
.desde { color: var(--suave); font-size: .8rem; }
.tel { display: inline-block; margin-left: 6px; text-decoration: none; font-size: 1rem; }
tr.baja td { background: var(--baja); } tr.baja .dias { color: var(--baja-t); font-weight: 600; }
tr.media td { background: var(--media); } tr.media .dias { color: var(--media-t); font-weight: 600; }
tr.alta td { background: var(--alta); } tr.alta .dias { color: var(--alta-t); font-weight: 700; }
tfoot td { font-weight: 700; background: var(--chip); }
.vacio { text-align: center; color: var(--suave); padding: 24px; }
.nota { color: var(--suave); font-size: .8rem; margin-top: 12px; }
[hidden] { display: none !important; }
__CSS_SIN_JS__
</style>
</head>
<body>
<main>
  __ARRIBA__
  <h1>Pendientes por cobrar</h1>
  <div class="gen">Actualizado el __GENERADO__</div>

  <div class="resumen">
    <div class="kpi"><b id="kTotal">__KTOTAL__</b><span>Total por cobrar</span></div>
    <div class="kpi"><b id="kClientes">__KCLIENTES__</b><span>Clientes</span></div>
  </div>

  <noscript><p class="nota" style="margin:0 0 10px">Toque los títulos para ordenar y los botones para
  filtrar. Para <b>buscar por nombre</b>, abra este archivo con Chrome.</p></noscript>

  <div id="sinjs">__SIN_JS__</div>

  <div id="conjs" hidden>
  <input type="search" id="buscar" placeholder="Buscar cliente…" autocomplete="off">

  <div class="chips" id="chips">
    <button data-min="0" class="on">Todos</button>
    <button data-min="15">15+ días</button>
    <button data-min="30">30+ días</button>
    <button data-min="60">60+ días</button>
  </div>

  <table>
    <thead><tr>
      <th data-col="n">Cliente</th>
      <th data-col="d" class="num">Deuda</th>
      <th data-col="x" class="num">Días</th>
    </tr></thead>
    <tbody id="filas"></tbody>
    <tfoot><tr><td id="pieTxt">Total</td><td class="num" id="pieTotal"></td><td></td></tr></tfoot>
  </table>
  </div>

  <p class="nota">Toca el título de una columna para ordenar; tócalo otra vez para invertir.
  Colores: amarillo 15+ días · naranja 30+ · rojo 60+. 📞 llama al cliente.</p>
</main>

<script>
var DATOS = __DATOS__;
// Con JavaScript (Chrome) se usa la versión con búsqueda; la otra queda
// para los visores que no lo ejecutan (WhatsApp, visor de Android).
document.getElementById("sinjs").hidden = true;
document.getElementById("conjs").hidden = false;
var orden = { col: "d", desc: true };
var minDias = 0;

function pesos(v) { return "$" + Math.round(v).toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, "."); }
function sinTildes(s) { return s.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase(); }
function nivel(d) { d = d || 0; return d >= 60 ? "alta" : d >= 30 ? "media" : d >= 15 ? "baja" : ""; }
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) {
  return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

function pintar() {
  var q = sinTildes(document.getElementById("buscar").value.trim());
  var filas = DATOS.filter(function (r) {
    return (r.x || 0) >= minDias && (!q || sinTildes(r.n).indexOf(q) !== -1);
  });
  filas.sort(function (a, b) {
    var r;
    if (orden.col === "n") r = a.n.localeCompare(b.n, "es", { sensitivity: "base" });
    else r = (a[orden.col] == null ? -1 : a[orden.col]) - (b[orden.col] == null ? -1 : b[orden.col]);
    return orden.desc ? -r : r;
  });

  var html = "", total = 0;
  filas.forEach(function (r) {
    total += r.d;
    html += '<tr class="' + nivel(r.x) + '"><td>' +
      (r.u ? '<a class="nombre" href="' + esc(r.u) + '">' + esc(r.n) + "</a>"
           : '<span class="nombre">' + esc(r.n) + "</span>") +
      (r.t ? '<a class="tel" href="tel:' + esc(r.t) + '" aria-label="Llamar">📞</a>' : "") +
      (r.f ? '<div class="desde">debe desde el ' + esc(r.f) + "</div>" : "") +
      '</td><td class="num">' + pesos(r.d) + '</td><td class="num dias">' +
      (r.x == null ? "" : r.x) + "</td></tr>";
  });
  if (!filas.length) html = '<tr><td colspan="3" class="vacio">No hay clientes con ese filtro</td></tr>';
  document.getElementById("filas").innerHTML = html;
  document.getElementById("pieTxt").textContent = "Total (" + filas.length + ")";
  document.getElementById("pieTotal").textContent = pesos(total);

  document.querySelectorAll("th").forEach(function (th) {
    var t = th.textContent.replace(/ [▲▼]$/, "");
    th.textContent = th.dataset.col === orden.col ? t + (orden.desc ? " ▼" : " ▲") : t;
  });
}

document.querySelectorAll("th").forEach(function (th) {
  th.addEventListener("click", function () {
    var c = th.dataset.col;
    // Los nombres empiezan de la A a la Z; los números, de mayor a menor
    orden = orden.col === c ? { col: c, desc: !orden.desc } : { col: c, desc: c !== "n" };
    pintar();
  });
});
document.getElementById("chips").addEventListener("click", function (e) {
  var b = e.target.closest("button"); if (!b) return;
  minDias = +b.dataset.min;
  document.querySelectorAll("#chips button").forEach(function (x) { x.classList.toggle("on", x === b); });
  pintar();
});
document.getElementById("buscar").addEventListener("input", pintar);

var suma = DATOS.reduce(function (s, r) { return s + r.d; }, 0);
document.getElementById("kTotal").textContent = pesos(suma);
document.getElementById("kClientes").textContent = DATOS.length;
pintar();
</script>
</body>
</html>
"""
