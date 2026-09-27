import tkinter as tk
from tkinter import messagebox

import matplotlib
matplotlib.use("TkAgg")
import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from config.database import get_connection
from utils import metricas as M
from utils.conciliacion import nombre_mes
from utils.formatters import format_currency
from utils.graficos import Interactivo, escala_legible, formato_corto, formato_pesos
from utils.theme import FONT_HEADER, FONT_SMALL, kpi_card
from utils.ventanas import hacer_modal, centrar_ventana

# Paleta coherente con el tema Flatly
COLORES = ["#2c3e50", "#18bc9c", "#3498db", "#f39c12", "#e74c3c",
           "#9b59b6", "#1abc9c", "#34495e", "#95a5a6", "#d35400",
           "#7f8c8d", "#16a085"]


def _acortar(texto, largo=18):
    texto = str(texto)
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


class PanelWindow:
    """Panel de análisis: reproduce en la aplicación los informes que estaban
    en Power BI (páginas Ventas, Compras y Egresos)."""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Panel de Análisis")
        centrar_ventana(self.window, 1250, 780)
        self.window.minsize(1000, 620)
        hacer_modal(self.window, parent)

        conn = get_connection()
        try:
            self.meses = M.meses_disponibles(conn)
        finally:
            conn.close()

        self.mes = tk.StringVar(value="Todos los meses")
        self.mes.trace_add("write", lambda *_: self.refrescar())

        self._construir()
        self.refrescar()

    # ── Interfaz ─────────────────────────────────────────────────────────
    def _construir(self):
        cabecera = ttk.Frame(self.window, padding=(15, 12))
        cabecera.pack(fill=tk.X)
        ttk.Label(cabecera, text="📈 Panel de Análisis", font=FONT_HEADER).pack(side=tk.LEFT)

        ttk.Combobox(cabecera, textvariable=self.mes, state="readonly", width=20,
                     values=["Todos los meses"] + [nombre_mes(m) for m in self.meses]
                     ).pack(side=tk.RIGHT)
        ttk.Label(cabecera, text="Periodo:").pack(side=tk.RIGHT, padx=(0, 6))

        cuaderno = ttk.Notebook(self.window)
        cuaderno.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.paginas = {}
        for clave, titulo in [("ventas", "  Ventas  "), ("compras", "  Compras  "),
                              ("egresos", "  Egresos  ")]:
            marco = ttk.Frame(cuaderno)
            cuaderno.add(marco, text=titulo)
            tarjetas = ttk.Frame(marco, padding=(10, 10, 10, 0))
            tarjetas.pack(fill=tk.X)
            lienzo = ttk.Frame(marco, padding=10)
            lienzo.pack(fill=tk.BOTH, expand=True)
            self.paginas[clave] = {"tarjetas": tarjetas, "lienzo": lienzo, "canvas": None}

    def _mes_actual(self):
        elegido = self.mes.get()
        if elegido == "Todos los meses":
            return None
        for m in self.meses:
            if nombre_mes(m) == elegido:
                return m
        return None

    def _tarjetas(self, pagina, datos):
        marco = self.paginas[pagina]["tarjetas"]
        for hijo in marco.winfo_children():
            hijo.destroy()
        for etiqueta, valor, estilo in datos:
            tarjeta, _ = kpi_card(marco, etiqueta, valor, estilo)
            tarjeta.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)

    def _figura(self, pagina, filas, columnas):
        """Prepara el lienzo de gráficos de una pestaña y devuelve los ejes."""
        info = self.paginas[pagina]
        if info["canvas"]:
            info["canvas"].get_tk_widget().destroy()

        figura = Figure(figsize=(11, 5.2), dpi=96, facecolor="#ffffff")
        ejes = figura.subplots(filas, columnas)
        canvas = FigureCanvasTkAgg(figura, master=info["lienzo"])
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        info["canvas"] = canvas
        info["figura"] = figura
        info["inter"] = Interactivo(figura, canvas, self._detalle)
        return figura, (ejes if hasattr(ejes, "__len__") else [ejes])

    def _detalle(self, texto):
        """Al hacer clic en un elemento del gráfico se muestra su dato completo."""
        messagebox.showinfo("Detalle", texto)

    def _inter(self, pagina):
        return self.paginas[pagina]["inter"]

    # ── Gráficos ─────────────────────────────────────────────────────────
    def _barras_h(self, ax, datos, titulo, color="#3498db", pagina=None,
                  unidad="pesos"):
        if not datos:
            ax.text(0.5, 0.5, "Sin datos", ha="center", va="center")
            ax.set_axis_off()
            return
        invertidos = datos[::-1]
        nombres = [_acortar(d[0]) for d in invertidos]
        valores = [d[1] for d in invertidos]
        barras = ax.barh(nombres, valores, color=color)

        # El valor escrito al final de cada barra: así se lee sin pasar el ratón
        etiquetas = [formato_corto(v) if unidad == "pesos" else f"{v:,.0f}"
                     for v in valores]
        ax.bar_label(barras, labels=etiquetas, fontsize=7, padding=3)
        ax.set_xlim(0, max(valores) * 1.18 if max(valores) > 0 else 1)

        ax.set_title(titulo, fontsize=10, fontweight="bold")
        ax.tick_params(labelsize=7)
        ax.grid(axis="x", alpha=0.25)
        escala_legible(ax, "x")
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)

        if pagina:
            total = sum(valores) or 1
            for barra, (nombre, valor) in zip(barras, invertidos):
                detalle = (formato_pesos(valor) if unidad == "pesos"
                           else f"{valor:,.0f} unidades")
                self._inter(pagina).registrar(
                    barra, f"{nombre}\n{detalle}\n{valor / total * 100:.1f}% del total", ax)

    def _torta(self, ax, datos, titulo, pagina=None):
        datos = [(n, v) for n, v in datos if v and v > 0]
        if not datos:
            ax.text(0.5, 0.5, "Sin datos", ha="center", va="center")
            ax.set_axis_off()
            return
        # Las porciones pequeñas se agrupan: si no, las etiquetas se solapan
        datos = sorted(datos, key=lambda d: d[1], reverse=True)
        total_bruto = sum(d[1] for d in datos)
        grandes = [d for d in datos if d[1] / total_bruto >= 0.03]
        resto = sum(d[1] for d in datos if d[1] / total_bruto < 0.03)
        if resto:
            grandes.append(("Otros", resto))
        datos = grandes
        total = sum(d[1] for d in datos)

        def etiqueta_pct(pct):
            # Debajo del 5 % solo el porcentaje: el importe no cabe
            if pct < 5:
                return f"{pct:.0f}%"
            return f"{pct:.0f}%\n{formato_corto(pct * total / 100)}"

        porciones, _, _ = ax.pie(
            [d[1] for d in datos],
            labels=[_acortar(d[0], 14) for d in datos],
            autopct=etiqueta_pct, pctdistance=0.68, labeldistance=1.06,
            textprops={"fontsize": 6.5}, colors=COLORES[:len(datos)],
            wedgeprops={"edgecolor": "white", "linewidth": 1})
        ax.set_title(titulo, fontsize=10, fontweight="bold")

        if pagina:
            for porcion, (nombre, valor) in zip(porciones, datos):
                self._inter(pagina).registrar(
                    porcion, f"{nombre}\n{formato_pesos(valor)}\n"
                             f"{valor / total * 100:.1f}% del total", ax)

    def _linea(self, ax, datos, titulo, color="#18bc9c", pagina=None):
        if not datos:
            ax.text(0.5, 0.5, "Sin datos", ha="center", va="center")
            ax.set_axis_off()
            return
        etiquetas = [d[0] for d in datos]
        valores = [d[1] for d in datos]
        ax.plot(etiquetas, valores, color=color, linewidth=2, zorder=1)

        for i, (x, v) in enumerate(zip(etiquetas, valores)):
            punto = ax.plot([x], [v], marker="o", markersize=7, color=color, zorder=2)[0]
            ax.annotate(formato_corto(v), (x, v), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=6.5)
            if pagina:
                anterior = valores[i - 1] if i else None
                extra = ""
                if anterior:
                    dif = (v - anterior) / abs(anterior) * 100
                    extra = f"\n{'+' if dif >= 0 else ''}{dif:.1f}% frente al mes anterior"
                self._inter(pagina).registrar(
                    punto, f"{nombre_mes(x) if '-' in str(x) else x}\n"
                           f"{formato_pesos(v)}{extra}", ax)

        margen = (max(valores) - min(valores)) * 0.18 or abs(max(valores)) * 0.2 or 1
        ax.set_ylim(min(valores) - margen, max(valores) + margen)
        ax.set_title(titulo, fontsize=10, fontweight="bold")
        ax.tick_params(labelsize=7, axis="x", rotation=45)
        ax.grid(alpha=0.25)
        escala_legible(ax, "y")
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)

    # ── Carga ────────────────────────────────────────────────────────────
    def refrescar(self):
        mes = self._mes_actual()
        conn = get_connection()
        try:
            self._pagina_ventas(conn, mes)
            self._pagina_compras(conn, mes)
            self._pagina_egresos(conn, mes)
        finally:
            conn.close()

    def _pagina_ventas(self, conn, mes):
        ingresos = M.total_ingresos(conn, mes)
        cogs = M.costo_mercancia_vendida(conn, mes)
        self._tarjetas("ventas", [
            ("Total ingresos", format_currency(ingresos), "primary"),
            ("Costo de lo vendido (COGS)", format_currency(cogs), "secondary"),
            ("Margen bruto = ingresos − COGS", format_currency(ingresos - cogs), "success"),
        ])
        figura, ejes = self._figura("ventas", 1, 3)
        self._torta(ejes[0], M.ingresos_por_producto(conn, mes, 8),
                    "Ingresos por producto", "ventas")
        self._barras_h(ejes[1], M.unidades_vendidas(conn, mes, 10),
                       "Unidades vendidas", "#18bc9c", "ventas", unidad="unidades")
        self._linea(ejes[2], M.ingresos_por_mes(conn), "Ingresos por mes",
                    pagina="ventas")
        figura.tight_layout()

    def _pagina_compras(self, conn, mes):
        self._tarjetas("compras", [
            ("Total compras", format_currency(M.total_compras(conn, mes)), "warning"),
            ("Flete", format_currency(M.total_flete(conn, mes)), "secondary"),
            ("IVA", format_currency(M.total_iva(conn, mes)), "secondary"),
        ])
        figura, ejes = self._figura("compras", 1, 2)
        self._barras_h(ejes[0], M.compras_por_producto(conn, mes, 12),
                       "Compras por producto", "#f39c12", "compras")
        self._barras_h(ejes[1], M.unidades_compradas(conn, mes, 12),
                       "Unidades compradas", "#2c3e50", "compras", unidad="unidades")
        figura.tight_layout()

    def _pagina_egresos(self, conn, mes):
        neta = M.utilidad_neta(conn, mes)
        self._tarjetas("egresos", [
            ("Utilidad neta", format_currency(neta),
             "success" if neta >= 0 else "danger"),
            ("Utilidad neta pagada", format_currency(M.utilidad_neta_pagada(conn, mes)), "info"),
            ("A cada socio", format_currency(M.rubro_a_cada_uno(conn, mes)), "primary"),
            ("Egresos con COGS", format_currency(M.egresos_con_cogs(conn, mes)), "warning"),
            ("Valor inventario", format_currency(M.valor_inventario(conn)), "secondary"),
        ])

        figura, ejes = self._figura("egresos", 1, 3)

        # Ingresos contra egresos, mes a mes
        meses = M.meses_disponibles(conn)
        ingresos = [M.total_ingresos(conn, m) for m in meses]
        egresos = [M.egresos_con_cogs(conn, m) for m in meses]
        ax = ejes[0]
        ancho = 0.4
        pos = range(len(meses))
        b1 = ax.bar([x - ancho / 2 for x in pos], ingresos, ancho,
                    label="Ingresos", color="#18bc9c")
        b2 = ax.bar([x + ancho / 2 for x in pos], egresos, ancho,
                    label="Egresos con COGS", color="#e74c3c")
        ax.set_xticks(list(pos))
        ax.set_xticklabels(meses, rotation=45, fontsize=7)
        ax.set_title("Ingresos frente a egresos", fontsize=10, fontweight="bold")
        ax.legend(fontsize=7)
        ax.grid(axis="y", alpha=0.25)
        escala_legible(ax, "y")
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)

        for barras, etiqueta, serie in [(b1, "Ingresos", ingresos),
                                        (b2, "Egresos con COGS", egresos)]:
            ax.bar_label(barras, labels=[formato_corto(v) for v in serie],
                         fontsize=5.5, padding=2, rotation=90)
            for barra, m, v, i, e in zip(barras, meses, serie, ingresos, egresos):
                margen = i - e
                self._inter("egresos").registrar(
                    barra, f"{nombre_mes(m)}\n{etiqueta}: {formato_pesos(v)}\n"
                           f"Utilidad del mes: {formato_pesos(margen)}", ax)

        # Evolución de la utilidad neta
        self._linea(ejes[1], M.serie_mensual(conn, M.utilidad_neta),
                    "Utilidad neta por mes", "#2c3e50", pagina="egresos")
        ejes[1].axhline(0, color="#e74c3c", linewidth=1, linestyle="--")

        self._torta(ejes[2], M.composicion_egresos(conn, mes),
                    "Composición de egresos", "egresos")
        figura.tight_layout()
