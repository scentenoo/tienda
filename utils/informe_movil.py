"""Informe de pendientes para el celular: un solo archivo HTML, sin nada
externo, que se manda por WhatsApp y se abre en el navegador del teléfono.

A diferencia del PDF, quien lo recibe puede ordenar tocando las columnas,
buscar por nombre y filtrar por días de mora, sin que haya que mandarle un
documento por cada orden.
"""
import json
from datetime import datetime
from html import escape
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
            .replace("__FILAS__", _filas_html(datos))
            .replace("__KTOTAL__", _pesos(total)).replace("__KCLIENTES__", str(len(datos)))
            .replace("__PIETXT__", f"Total ({len(datos)})").replace("__PIETOTAL__", _pesos(total))
            .replace("__DATOS__", json_datos).replace("__GENERADO__", generado))


def _pesos(v):
    return "$" + f"{round(v):,.0f}".replace(",", ".")


def _nivel(dias):
    dias = dias or 0
    return "alta" if dias >= 60 else "media" if dias >= 30 else "baja" if dias >= 15 else ""


def _filas_html(datos):
    """La tabla ya escrita, de quien más debe a quien menos. El visor de
    archivos de WhatsApp o de Android no ejecuta JavaScript: sin esto el
    informe se veía vacío. Con JavaScript, pintar() la reemplaza igual."""
    filas = []
    for r in sorted(datos, key=lambda r: r["d"], reverse=True):
        nombre = (f'<a class="nombre" href="{escape(r["u"])}">{escape(r["n"])}</a>' if r["u"]
                  else f'<span class="nombre">{escape(r["n"])}</span>')
        tel = (f'<a class="tel" href="tel:{escape(r["t"])}" aria-label="Llamar">📞</a>'
               if r["t"] else "")
        desde = f'<div class="desde">debe desde el {escape(r["f"])}</div>' if r["f"] else ""
        filas.append(f'<tr class="{_nivel(r["x"])}"><td>{nombre}{tel}{desde}</td>'
                     f'<td class="num">{_pesos(r["d"])}</td>'
                     f'<td class="num dias">{"" if r["x"] is None else r["x"]}</td></tr>')
    return "".join(filas) or '<tr><td colspan="3" class="vacio">No hay clientes con deuda</td></tr>'


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

  <input type="search" id="buscar" placeholder="Buscar cliente…" autocomplete="off" hidden>

  <div class="chips" id="chips" hidden>
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
    <tbody id="filas">__FILAS__</tbody>
    <tfoot><tr><td id="pieTxt">__PIETXT__</td><td class="num" id="pieTotal">__PIETOTAL__</td><td></td></tr></tfoot>
  </table>

  <p class="nota" id="notaOrden" hidden>Toca el título de una columna para ordenar; tócalo otra vez para invertir.
  Colores: amarillo 15+ días · naranja 30+ · rojo 60+. 📞 llama al cliente.</p>
</main>

<script>
var DATOS = __DATOS__;
// Buscar, filtrar y ordenar solo existen con JavaScript: sin él (visor de
// WhatsApp o de Android) se ve la tabla ya escrita, sin controles que no sirven.
["buscar", "chips", "notaOrden"].forEach(function (id) { document.getElementById(id).hidden = false; });
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
