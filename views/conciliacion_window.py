import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import ttkbootstrap as ttk

from config.database import get_connection
from utils.conciliacion import (MANUAL_AJUSTE, MANUAL_INICIO, borrar_giro,
                                calcular, deudores, guardar_giro,
                                telefonos_clientes,
                                informacion_adicional, listar_giros,
                                nombre_mes, resumen_socios, socios_conocidos)
from utils.formatters import format_currency
from utils.theme import FONT_BOLD, FONT_HEADER, FONT_SMALL, ROW_COLORS, kpi_card
from utils.ventanas import hacer_modal, centrar_ventana


# Tres niveles de mora, usados igual en pantalla y en el PDF
NIVELES_MORA = {
    "mora_alta":  {"background": "#f8d7da", "foreground": "#a3242f"},   # 60+
    "mora_media": {"background": "#ffe0b2", "foreground": "#a0522d"},   # 30+
    "mora_baja":  {"background": "#fff3cd", "foreground": "#9c6f11"},   # 15+
}


def nivel_mora(dias):
    dias = dias or 0
    if dias >= 60:
        return "mora_alta"
    if dias >= 30:
        return "mora_media"
    if dias >= 15:
        return "mora_baja"
    return ""


class ConciliacionWindow:
    """Conciliación de caja: el cuadro que antes vivía en el Excel, calculado
    en vivo desde la base. Las dos filas manuales y los giros a socios salen de
    sus propias tablas."""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Informes")
        centrar_ventana(self.window, 1200, 700)
        self.window.minsize(900, 500)
        hacer_modal(self.window, parent)

        self.mostrar_ocultas = tk.BooleanVar(value=False)
        self.rango = tk.StringVar(value="Últimos 6 meses")
        self.rango.trace_add("write", lambda *_: self.cargar())
        self.orden_pend = ("deuda", True)
        self.datos = None

        cuaderno = ttk.Notebook(self.window)
        cuaderno.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        pestana_conc = ttk.Frame(cuaderno)
        pestana_pend = ttk.Frame(cuaderno)
        pestana_giros = ttk.Frame(cuaderno)
        pestana_cap = ttk.Frame(cuaderno)
        cuaderno.add(pestana_conc, text="  Conciliación de Caja  ")
        cuaderno.add(pestana_pend, text="  Pendientes  ")
        cuaderno.add(pestana_giros, text="  Giros a Socios  ")
        cuaderno.add(pestana_cap, text="  Capital de Trabajo  ")

        self.setup_ui(pestana_conc)
        self.setup_pendientes(pestana_pend)
        self.setup_giros(pestana_giros)
        self.setup_capital(pestana_cap)
        self.cargar()
        self.cargar_pendientes()
        self.cargar_giros()
        self.cargar_capital()

    # ── Interfaz ─────────────────────────────────────────────────────────
    def setup_ui(self, contenedor):
        marco = ttk.Frame(contenedor, padding=15)
        marco.pack(fill=tk.BOTH, expand=True)

        cabecera = ttk.Frame(marco)
        cabecera.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(cabecera, text="💵 Conciliación de Caja", font=FONT_HEADER).pack(side=tk.LEFT)

        ttk.Button(cabecera, text="Actualizar", command=self.cargar,
                   bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="Exportar PDF", command=self.exportar_pdf,
                   bootstyle="info").pack(side=tk.RIGHT, padx=4)
        ttk.Checkbutton(cabecera, text="Ver filas ocultas",
                        variable=self.mostrar_ocultas, command=self.cargar,
                        bootstyle="round-toggle").pack(side=tk.RIGHT, padx=12)

        ttk.Combobox(cabecera, textvariable=self.rango, state="readonly", width=18,
                     values=["Últimos 6 meses", "Últimos 12 meses", "Todos los meses"]
                     ).pack(side=tk.RIGHT, padx=4)
        ttk.Label(cabecera, text="Ver:").pack(side=tk.RIGHT)

        tabla = ttk.Frame(marco)
        tabla.pack(fill=tk.BOTH, expand=True)
        tabla.rowconfigure(0, weight=1)
        tabla.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tabla, show="headings", bootstyle="primary")
        barra_v = ttk.Scrollbar(tabla, orient=tk.VERTICAL, command=self.tree.yview)
        barra_h = ttk.Scrollbar(tabla, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=barra_v.set, xscrollcommand=barra_h.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        barra_v.grid(row=0, column=1, sticky="ns")
        barra_h.grid(row=1, column=0, sticky="ew")

        self.tree.tag_configure("seccion", font=FONT_BOLD, **ROW_COLORS["info"])
        self.tree.tag_configure("total", font=FONT_BOLD, background="#eaeded")
        self.tree.tag_configure("positivo", font=FONT_BOLD, **ROW_COLORS["success"])
        self.tree.tag_configure("negativo", font=FONT_BOLD, **ROW_COLORS["danger"])
        self.tree.tag_configure("manual", **ROW_COLORS["warning"])
        self.tree.tag_configure("oculta", foreground="#95a5a6")

        self.tree.bind("<Double-1>", self._doble_clic)
        self.tree.bind("<Button-3>", self._menu_contextual)

        pie = ttk.Frame(marco)
        pie.pack(fill=tk.X, pady=(10, 0))
        self.etiqueta_info = ttk.Label(pie, text="", font=FONT_SMALL, bootstyle="secondary")
        self.etiqueta_info.pack(side=tk.LEFT)
        ttk.Label(pie, text="Doble clic en una fila amarilla para editarla  ·  "
                           "Clic derecho para ocultar",
                  font=FONT_SMALL, bootstyle="secondary").pack(side=tk.RIGHT)

    # ── Datos ────────────────────────────────────────────────────────────
    def _ocultas(self, conn):
        return {f[0] for f in conn.execute("SELECT concepto FROM conciliacion_filas_ocultas")}

    def cargar(self):
        conn = get_connection()
        try:
            from utils.conciliacion import meses_con_datos
            meses = meses_con_datos(conn)
            limite = {"Últimos 6 meses": 6, "Últimos 12 meses": 12}.get(self.rango.get())
            # El acumulado siempre es de todo el histórico, aunque se vean menos meses
            completo = calcular(conn, meses)
            self.datos = calcular(conn, meses[-limite:]) if limite else completo
            self.datos["acumulado"] = completo["acumulado"]
            ocultas = self._ocultas(conn)
            info = informacion_adicional(conn)
        finally:
            conn.close()

        d = self.datos
        # El acumulado va justo después del concepto: con muchos meses, si va al
        # final se pierde de vista al desplazarse.
        columnas = ["concepto", "total"] + d["meses"]
        self.tree.configure(columns=columnas)
        self.tree.heading("concepto", text="CONCEPTO")
        self.tree.column("concepto", width=270, anchor=tk.W, stretch=False)
        self.tree.heading("total", text="ACUMULADO")
        self.tree.column("total", width=160, anchor=tk.E, stretch=False)
        for mes, titulo in zip(d["meses"], d["encabezados"]):
            self.tree.heading(mes, text=titulo)
            self.tree.column(mes, width=135, anchor=tk.E, stretch=False)

        self.tree.delete(*self.tree.get_children())
        for tipo, concepto in d["filas"]:
            oculta = concepto in ocultas
            if oculta and not self.mostrar_ocultas.get():
                continue

            if tipo == "seccion":
                valores = [concepto] + [""] * (len(d["meses"]) + 1)
                etiquetas = ("seccion",)
            else:
                fila = d["valores"][concepto]
                valores = ([concepto, format_currency(d["acumulado"][concepto])]
                           + [format_currency(v) for v in fila])
                if tipo == "neto":
                    etiquetas = ("positivo" if d["acumulado"][concepto] >= 0 else "negativo",)
                elif tipo == "total":
                    etiquetas = ("total",)
                elif tipo == "manual":
                    etiquetas = ("manual",)
                else:
                    etiquetas = ()

            if oculta:
                etiquetas = etiquetas + ("oculta",)
            self.tree.insert("", tk.END, iid=concepto, values=valores, tags=etiquetas)

        self.etiqueta_info.config(
            text=f"Cuentas por cobrar: {format_currency(info['cuentas_por_cobrar'])} "
                 f"({info['clientes_con_deuda']} clientes)   ·   "
                 f"Pérdidas registradas: {format_currency(info['perdidas'])}")

    # ── Acciones ─────────────────────────────────────────────────────────
    def _fila_seleccionada(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _doble_clic(self, event=None):
        concepto = self._fila_seleccionada()
        if concepto in (MANUAL_INICIO, MANUAL_AJUSTE):
            EditorManual(self.window, concepto, self.datos["meses"], self.cargar)

    def _menu_contextual(self, event):
        fila = self.tree.identify_row(event.y)
        if not fila:
            return
        self.tree.selection_set(fila)

        conn = get_connection()
        try:
            oculta = fila in self._ocultas(conn)
        finally:
            conn.close()

        menu = tk.Menu(self.window, tearoff=0)
        if oculta:
            menu.add_command(label=f"Mostrar «{fila}»", command=lambda: self._alternar(fila, False))
        else:
            menu.add_command(label=f"Ocultar «{fila}»", command=lambda: self._alternar(fila, True))
        menu.add_separator()
        menu.add_command(label="Mostrar todas las filas", command=self._mostrar_todas)
        menu.tk_popup(event.x_root, event.y_root)

    def _alternar(self, concepto, ocultar):
        conn = get_connection()
        try:
            if ocultar:
                conn.execute("INSERT OR IGNORE INTO conciliacion_filas_ocultas (concepto) VALUES (?)",
                             (concepto,))
            else:
                conn.execute("DELETE FROM conciliacion_filas_ocultas WHERE concepto = ?", (concepto,))
            conn.commit()
        finally:
            conn.close()
        self.cargar()

    def _mostrar_todas(self):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM conciliacion_filas_ocultas")
            conn.commit()
        finally:
            conn.close()
        self.cargar()

    # ── Pendientes ───────────────────────────────────────────────────────
    def setup_pendientes(self, contenedor):
        marco = ttk.Frame(contenedor, padding=15)
        marco.pack(fill=tk.BOTH, expand=True)

        cabecera = ttk.Frame(marco)
        cabecera.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(cabecera, text="📋 Clientes con deuda", font=FONT_HEADER).pack(side=tk.LEFT)
        ttk.Button(cabecera, text="Actualizar", command=self.cargar_pendientes,
                   bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="Exportar PDF", command=self.exportar_pendientes_pdf,
                   bootstyle="info").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="📱 Enviar al celular", command=self.exportar_pendientes_movil,
                   bootstyle="success").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="📄 Estado de cuenta", command=self.estado_cuenta_sel,
                   bootstyle="primary").pack(side=tk.RIGHT, padx=4)

        columnas = ("cliente", "deuda", "desde", "dias")
        self.tree_pend = ttk.Treeview(marco, columns=columnas, show="headings",
                                      bootstyle="primary")
        for col, titulo, ancho, anclaje in [
                ("cliente", "Cliente", 320, tk.W), ("deuda", "Deuda", 140, tk.E),
                ("desde", "Debe desde", 160, tk.W), ("dias", "Días", 80, tk.E)]:
            self.tree_pend.heading(col, text=titulo)
            self.tree_pend.column(col, width=ancho, anchor=anclaje)

        barra = ttk.Scrollbar(marco, orient=tk.VERTICAL, command=self.tree_pend.yview)
        self.tree_pend.configure(yscrollcommand=barra.set)
        self.tree_pend.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        barra.pack(side=tk.RIGHT, fill=tk.Y)

        # Cuanto más vieja la deuda, más llama la atención
        for nombre, colores in NIVELES_MORA.items():
            self.tree_pend.tag_configure(nombre, **colores)

        for col in columnas:
            self.tree_pend.heading(col, command=lambda c=col: self.ordenar_pendientes(c))
        self.tree_pend.bind("<Double-1>", lambda e: self.estado_cuenta_sel())

        pie = ttk.Frame(contenedor)
        pie.pack(fill=tk.X, padx=25, pady=(0, 10))
        ttk.Label(pie, text="Mora:  15+ días amarillo  ·  30+ naranja  ·  60+ rojo",
                  font=FONT_SMALL, bootstyle="secondary").pack(side=tk.LEFT)
        self.etiqueta_pend = ttk.Label(pie, text="", font=FONT_BOLD)
        self.etiqueta_pend.pack(side=tk.RIGHT)

    def cargar_pendientes(self):
        conn = get_connection()
        try:
            self.filas_pend = deudores(conn)
        finally:
            conn.close()
        self._pintar_pendientes()

    def ordenar_pendientes(self, columna):
        """Ordena por la columna pulsada; al repetir, invierte el sentido."""
        if self.orden_pend[0] == columna:
            self.orden_pend = (columna, not self.orden_pend[1])
        else:
            # Los textos empiezan ascendentes; los números, descendentes
            self.orden_pend = (columna, columna in ("deuda", "dias"))

        indice = {"cliente": 0, "deuda": 1, "desde": 3, "dias": 3}[columna]
        def clave(f):
            v = f[indice]
            if indice == 0:
                return str(v).lower()
            return v if v is not None else -1

        self.filas_pend.sort(key=clave, reverse=self.orden_pend[1])
        self._pintar_pendientes()

    def _pintar_pendientes(self):
        self.tree_pend.delete(*self.tree_pend.get_children())
        total = 0.0
        for nombre, deuda, desde, dias in self.filas_pend:
            total += deuda
            self.tree_pend.insert("", tk.END, tags=(nivel_mora(dias),), values=(
                nombre, format_currency(deuda), desde or "", dias if dias is not None else ""))

        for col, titulo in [("cliente", "Cliente"), ("deuda", "Deuda"),
                            ("desde", "Debe desde"), ("dias", "Días")]:
            flecha = ""
            if self.orden_pend[0] == col:
                flecha = "  ▼" if self.orden_pend[1] else "  ▲"
            self.tree_pend.heading(col, text=titulo + flecha)

        self.total_pend = total
        self.etiqueta_pend.config(
            text=f"{len(self.filas_pend)} clientes  ·  Total: {format_currency(total)}")

    def exportar_pendientes_pdf(self):
        from utils.pdf import exportar_pendientes
        try:
            ruta = exportar_pendientes(self.filas_pend, self.total_pend)
            messagebox.showinfo("PDF generado", f"Guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}")

    def estado_cuenta_sel(self):
        """PDF con las compras y abonos del cliente seleccionado."""
        from utils.estado_cuenta import generar_y_abrir
        sel = self.tree_pend.selection()
        if not sel:
            messagebox.showinfo("Estado de cuenta", "Seleccione un cliente de la lista.")
            return
        nombre = self.tree_pend.item(sel[0], "values")[0]
        conn = get_connection()
        try:
            fila = conn.execute("SELECT id FROM clients WHERE name = ?", (nombre,)).fetchone()
        finally:
            conn.close()
        if fila:
            generar_y_abrir(fila[0])

    def exportar_pendientes_movil(self):
        """HTML interactivo para mandar por WhatsApp: se ordena y filtra en el
        teléfono, así no hay que mandar un PDF por cada orden."""
        import os
        from utils.informe_movil import exportar_pendientes_html
        try:
            conn = get_connection()
            try:
                telefonos = telefonos_clientes(conn)
            finally:
                conn.close()
            ruta = exportar_pendientes_html(self.filas_pend, telefonos)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el informe:\n{e}")
            return
        messagebox.showinfo(
            "Informe para el celular",
            f"Guardado en:\n{ruta}\n\nMándalo por WhatsApp como documento. "
            "En el teléfono se abre con Chrome y se puede ordenar tocando las columnas.")
        if hasattr(os, "startfile"):
            os.startfile(ruta.parent)

    # ── Giros a socios ───────────────────────────────────────────────────
    def setup_giros(self, contenedor):
        marco = ttk.Frame(contenedor, padding=15)
        marco.pack(fill=tk.BOTH, expand=True)

        cabecera = ttk.Frame(marco)
        cabecera.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(cabecera, text="🤝 Giros a Socios", font=FONT_HEADER).pack(side=tk.LEFT)
        ttk.Button(cabecera, text="Eliminar", command=self.borrar_giro_sel,
                   bootstyle="danger-outline").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="Editar", command=self.editar_giro,
                   bootstyle="secondary").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="+ Nuevo giro", command=self.nuevo_giro,
                   bootstyle="success").pack(side=tk.RIGHT, padx=4)

        cuerpo = ttk.Frame(marco)
        cuerpo.pack(fill=tk.BOTH, expand=True)

        columnas = ("fecha", "socio", "monto", "tipo", "concepto")
        self.tree_giros = ttk.Treeview(cuerpo, columns=columnas, show="headings",
                                       bootstyle="primary")
        for col, titulo, ancho, anclaje in [
                ("fecha", "Fecha", 100, tk.W), ("socio", "Socio", 130, tk.W),
                ("monto", "Monto", 140, tk.E), ("tipo", "Tipo", 100, tk.W),
                ("concepto", "Concepto", 300, tk.W)]:
            self.tree_giros.heading(col, text=titulo)
            self.tree_giros.column(col, width=ancho, anchor=anclaje)
        self.tree_giros.tag_configure("reinversion", **ROW_COLORS["info"])
        self.tree_giros.bind("<Double-1>", lambda e: self.editar_giro())

        barra = ttk.Scrollbar(cuerpo, orient=tk.VERTICAL, command=self.tree_giros.yview)
        self.tree_giros.configure(yscrollcommand=barra.set)
        self.tree_giros.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        barra.pack(side=tk.LEFT, fill=tk.Y)

        # Resumen por socio, como el cuadro de la derecha en el Excel
        panel = ttk.Labelframe(cuerpo, text="Resumen por socio", padding=12)
        panel.pack(side=tk.LEFT, fill=tk.Y, padx=(15, 0))
        self.marco_resumen = ttk.Frame(panel)
        self.marco_resumen.pack(fill=tk.BOTH, expand=True)

    def cargar_giros(self):
        conn = get_connection()
        try:
            filas = listar_giros(conn)
            resumen = resumen_socios(conn)
        finally:
            conn.close()

        self.tree_giros.delete(*self.tree_giros.get_children())
        for gid, fecha, socio, monto, concepto, tipo in filas:
            etiqueta = ("reinversion",) if tipo == "reinversion" else ()
            self.tree_giros.insert("", tk.END, iid=str(gid), tags=etiqueta, values=(
                fecha, socio, format_currency(monto),
                "Reinversión" if tipo == "reinversion" else "Giro", concepto))

        for hijo in self.marco_resumen.winfo_children():
            hijo.destroy()
        for socio, giros, reinv, total in resumen:
            fila = ttk.Frame(self.marco_resumen)
            fila.pack(fill=tk.X, pady=4)
            ttk.Label(fila, text=socio, font=FONT_BOLD, width=12).pack(anchor=tk.W)
            ttk.Label(fila, text=format_currency(total), font=FONT_BOLD,
                      bootstyle="primary").pack(anchor=tk.W)
            if reinv:
                ttk.Label(fila, text=f"giros {format_currency(giros)} · "
                                     f"reinv. {format_currency(reinv)}",
                          font=FONT_SMALL, bootstyle="secondary").pack(anchor=tk.W)

    def _giro_seleccionado(self):
        sel = self.tree_giros.selection()
        return int(sel[0]) if sel else None

    def nuevo_giro(self):
        EditorGiro(self.window, None, self._tras_editar)

    def editar_giro(self):
        gid = self._giro_seleccionado()
        if not gid:
            messagebox.showinfo("Información", "Seleccione un movimiento primero")
            return
        EditorGiro(self.window, gid, self._tras_editar)

    def borrar_giro_sel(self):
        gid = self._giro_seleccionado()
        if not gid:
            messagebox.showinfo("Información", "Seleccione un movimiento primero")
            return
        valores = self.tree_giros.item(str(gid), "values")
        if not messagebox.askyesno("Confirmar",
                                   f"¿Eliminar el movimiento de {valores[1]} "
                                   f"por {valores[2]} del {valores[0]}?"):
            return
        conn = get_connection()
        try:
            borrar_giro(conn, gid)
        finally:
            conn.close()
        self._tras_editar()

    def _tras_editar(self):
        """Un giro cambia también la conciliación, así que se recarga todo."""
        self.cargar_giros()
        self.cargar()

    # ── Capital de trabajo ───────────────────────────────────────────────
    def setup_capital(self, contenedor):
        marco = ttk.Frame(contenedor, padding=15)
        marco.pack(fill=tk.BOTH, expand=True)

        cabecera = ttk.Frame(marco)
        cabecera.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(cabecera, text="🏦 Capital de Trabajo", font=FONT_HEADER).pack(side=tk.LEFT)
        ttk.Button(cabecera, text="Actualizar", command=self.cargar_capital,
                   bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=4)
        ttk.Button(cabecera, text="Exportar PDF", command=self.exportar_capital_pdf,
                   bootstyle="info").pack(side=tk.RIGHT, padx=4)

        # Lo primero que se ve: cuánto se puede sacar hoy
        self.ahora_cap = ttk.Labelframe(marco, text="¿Cuánto puedo girar ahora mismo?",
                                        padding=12)
        self.ahora_cap.pack(fill=tk.X, pady=(0, 12))

        self.tarjetas_cap = ttk.Frame(marco)
        self.tarjetas_cap.pack(fill=tk.X, pady=(0, 12))

        self.avisos_cap = ttk.Frame(marco)
        self.avisos_cap.pack(fill=tk.X, pady=(0, 12))

        cuerpo = ttk.Frame(marco)
        cuerpo.pack(fill=tk.BOTH, expand=True)

        izq = ttk.Labelframe(cuerpo, text="Cuánto se podía girar cada mes", padding=8)
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cols = ("mes", "utilidad", "cartera", "girable", "girado", "exceso")
        self.tree_cap = ttk.Treeview(izq, columns=cols, show="headings", height=9,
                                     bootstyle="primary")
        for col, titulo, ancho in [("mes", "Mes", 90), ("utilidad", "Utilidad", 135),
                                   ("cartera", "Se fue a fiado", 135),
                                   ("girable", "Girable", 135), ("girado", "Girado", 135),
                                   ("exceso", "Exceso", 135)]:
            self.tree_cap.heading(col, text=titulo)
            self.tree_cap.column(col, width=ancho, anchor=tk.E if col != "mes" else tk.W)
        self.tree_cap.tag_configure("exceso", **ROW_COLORS["danger"])
        self.tree_cap.tag_configure("holgado", **ROW_COLORS["success"])
        self.tree_cap.pack(fill=tk.BOTH, expand=True)

        der = ttk.Labelframe(cuerpo, text="Inventario por debajo del objetivo", padding=8)
        der.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        cols2 = ("producto", "stock", "objetivo", "faltan")
        self.tree_inv = ttk.Treeview(der, columns=cols2, show="headings", height=9,
                                     bootstyle="warning")
        for col, titulo, ancho in [("producto", "Producto", 190), ("stock", "Stock", 70),
                                   ("objetivo", "Objetivo", 80), ("faltan", "Faltan", 110)]:
            self.tree_inv.heading(col, text=titulo)
            self.tree_inv.column(col, width=ancho, anchor=tk.E if col != "producto" else tk.W)
        self.tree_inv.pack(fill=tk.BOTH, expand=True)

    def cargar_capital(self):
        from utils.capital import (DIAS_COBERTURA, diagnostico, girable_ahora,
                                   girable_por_mes, inventario_objetivo, situacion)
        conn = get_connection()
        try:
            self.cap = situacion(conn)
            self.cap_ahora = girable_ahora(conn)
            self.cap_meses = girable_por_mes(conn)
            self.cap_inv = inventario_objetivo(conn)
            avisos = diagnostico(conn)
        finally:
            conn.close()

        s = self.cap
        for hijo in self.ahora_cap.winfo_children():
            hijo.destroy()

        g = self.cap_ahora
        cuenta = ttk.Frame(self.ahora_cap)
        cuenta.pack(side=tk.LEFT, padx=(0, 30))
        for etiqueta, valor, estilo in [
                ("Efectivo real (contado y abonos cobrados)", g["efectivo"], "secondary"),
                ("(−) Reponer inventario", -g["reponer_inventario"], "warning"),
                ("(−) Colchón de operación", -g["colchon"], "warning")]:
            fila = ttk.Frame(cuenta)
            fila.pack(fill=tk.X, pady=1)
            ttk.Label(fila, text=etiqueta, font=FONT_SMALL, width=38,
                      bootstyle=estilo).pack(side=tk.LEFT)
            ttk.Label(fila, text=format_currency(valor), font=FONT_SMALL,
                      bootstyle=estilo).pack(side=tk.RIGHT)

        hay = g["disponible"] > 0
        destaque = ttk.Frame(self.ahora_cap)
        destaque.pack(side=tk.LEFT)
        ttk.Label(destaque, text="DISPONIBLE PARA GIRAR", font=FONT_SMALL,
                  bootstyle="secondary").pack(anchor=tk.W)
        ttk.Label(destaque, text=format_currency(g["disponible"]),
                  font=(FONT_HEADER[0], 22, "bold"),
                  bootstyle="success" if hay else "danger").pack(anchor=tk.W)
        detalle = (f"{format_currency(g['por_socio'])} por cada uno de los "
                   f"{g['socios']} socios" if hay else
                   f"Faltan {format_currency(g['faltante'])} para poder girar algo")
        ttk.Label(destaque, text=detalle, font=FONT_SMALL,
                  bootstyle="success" if hay else "danger").pack(anchor=tk.W)

        for hijo in self.tarjetas_cap.winfo_children():
            hijo.destroy()
        tarjetas = [
            ("EFECTIVO LIBRE (caja)", s["efectivo_libre"],
             "success" if s["efectivo_libre"] >= 1_000_000 else "danger"),
            ("Atrapado en inventario", s["inventario"], "secondary"),
            ("Atrapado en fiado", s["cartera"], "warning"),
            ("Capital disponible", s["disponible"], "primary"),
        ]
        for etiqueta, valor, estilo in tarjetas:
            tarjeta, _ = kpi_card(self.tarjetas_cap, etiqueta, format_currency(valor), estilo)
            tarjeta.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        for hijo in self.avisos_cap.winfo_children():
            hijo.destroy()
        for nivel, texto in avisos:
            ttk.Label(self.avisos_cap, text=f"•  {texto}", font=FONT_SMALL,
                      bootstyle=nivel, wraplength=1100).pack(anchor=tk.W, pady=1)

        self.tree_cap.delete(*self.tree_cap.get_children())
        for m in self.cap_meses:
            etiqueta = ("exceso",) if m["exceso"] > 0 else ("holgado",)
            self.tree_cap.insert("", tk.END, tags=etiqueta, values=(
                nombre_mes(m["mes"]), format_currency(m["utilidad"]),
                format_currency(m["delta_cartera"]), format_currency(m["girable"]),
                format_currency(m["girado"]),
                format_currency(m["exceso"]) if m["exceso"] > 0 else "—"))

        self.tree_inv.delete(*self.tree_inv.get_children())
        for f in self.cap_inv["faltantes"]:
            self.tree_inv.insert("", tk.END, values=(
                f["producto"], f"{f['stock']:.1f}", f"{f['objetivo']:.1f}",
                format_currency(f["faltan_pesos"])))

    def exportar_capital_pdf(self):
        from utils.pdf import exportar_capital
        try:
            ruta = exportar_capital(self.cap, self.cap_meses, self.cap_inv,
                                    self.cap_ahora)
            messagebox.showinfo("PDF generado", f"Guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}")

    def exportar_pdf(self):
        from utils.pdf import exportar_conciliacion
        conn = get_connection()
        try:
            ocultas = self._ocultas(conn)
        finally:
            conn.close()
        try:
            ruta = exportar_conciliacion(self.datos, ocultas)
            messagebox.showinfo("PDF generado", f"Guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}")


class EditorManual:
    """Edita mes a mes una de las dos filas que se teclean a mano."""

    def __init__(self, parent, concepto, meses, al_guardar):
        self.concepto = concepto
        self.meses = meses
        self.al_guardar = al_guardar

        self.window = tk.Toplevel(parent)
        self.window.title(concepto)
        alto = min(180 + 34 * len(meses), 620)
        self.window.geometry(f"420x{alto}")
        self.window.resizable(False, True)
        hacer_modal(self.window, parent)

        marco = ttk.Frame(self.window, padding=18)
        marco.pack(fill=tk.BOTH, expand=True)
        ttk.Label(marco, text=concepto, font=FONT_BOLD, wraplength=370).pack(anchor=tk.W, pady=(0, 12))

        conn = get_connection()
        try:
            actuales = {f[0]: f[1] for f in conn.execute(
                "SELECT mes, monto FROM conciliacion_manual WHERE concepto = ?", (concepto,))}
        finally:
            conn.close()

        self.campos = {}
        for mes in meses:
            fila = ttk.Frame(marco)
            fila.pack(fill=tk.X, pady=3)
            ttk.Label(fila, text=nombre_mes(mes), width=18).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(int(actuales.get(mes, 0) or 0)))
            ttk.Entry(fila, textvariable=var, width=16, justify=tk.RIGHT).pack(side=tk.RIGHT)
            self.campos[mes] = var

        botones = ttk.Frame(marco)
        botones.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(botones, text="Guardar", command=self.guardar,
                   bootstyle="success").pack(side=tk.RIGHT, padx=4)
        ttk.Button(botones, text="Cancelar", command=self.window.destroy,
                   bootstyle="secondary").pack(side=tk.RIGHT)

    def guardar(self):
        valores = {}
        for mes, var in self.campos.items():
            texto = var.get().strip().replace(",", "").replace(".", "") or "0"
            try:
                valores[mes] = float(texto)
            except ValueError:
                messagebox.showerror("Valor inválido",
                                     f"«{var.get()}» no es un número ({nombre_mes(mes)})")
                return

        conn = get_connection()
        try:
            for mes, monto in valores.items():
                conn.execute("""INSERT INTO conciliacion_manual (mes, concepto, monto)
                                VALUES (?,?,?)
                                ON CONFLICT (mes, concepto) DO UPDATE SET monto = excluded.monto""",
                             (mes, self.concepto, monto))
            conn.commit()
        finally:
            conn.close()

        self.window.destroy()
        self.al_guardar()


class EditorGiro:
    """Alta y edición de un movimiento hacia un socio."""

    def __init__(self, parent, giro_id, al_guardar):
        self.giro_id = giro_id
        self.al_guardar = al_guardar

        self.window = tk.Toplevel(parent)
        self.window.title("Editar movimiento" if giro_id else "Nuevo giro a socio")
        self.window.geometry("470x430")
        self.window.resizable(False, False)
        hacer_modal(self.window, parent)

        conn = get_connection()
        try:
            socios = socios_conocidos(conn)
            datos = None
            if giro_id:
                datos = conn.execute(
                    "SELECT fecha, socio, monto, COALESCE(concepto,''), tipo "
                    "FROM giros_socios WHERE id = ?", (giro_id,)).fetchone()
        finally:
            conn.close()

        marco = ttk.Frame(self.window, padding=20)
        marco.pack(fill=tk.BOTH, expand=True)

        hoy = datetime.now().strftime("%Y-%m-%d")
        self.fecha    = tk.StringVar(value=datos[0] if datos else hoy)
        self.socio    = tk.StringVar(value=datos[1] if datos else (socios[0] if socios else ""))
        self.monto    = tk.StringVar(value=str(int(datos[2])) if datos else "")
        self.concepto = tk.StringVar(value=datos[3] if datos else "")
        self.tipo     = tk.StringVar(value=datos[4] if datos else "giro")

        # Tipo de movimiento, arriba y bien visible: cambia el significado de todo
        tipo_marco = ttk.Labelframe(marco, text="Tipo de movimiento", padding=10)
        tipo_marco.pack(fill=tk.X, pady=(0, 14))
        ttk.Radiobutton(tipo_marco, text="Giro  (sale dinero de la caja)",
                        variable=self.tipo, value="giro",
                        bootstyle="warning").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(tipo_marco, text="Reinversión  (no afecta la conciliación)",
                        variable=self.tipo, value="reinversion",
                        bootstyle="info").pack(anchor=tk.W, pady=2)

        def campo(etiqueta, constructor):
            fila = ttk.Frame(marco)
            fila.pack(fill=tk.X, pady=7)
            ttk.Label(fila, text=etiqueta, width=11).pack(side=tk.LEFT)
            widget = constructor(fila)
            widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
            return widget

        campo("Fecha", lambda p: ttk.Entry(p, textvariable=self.fecha))
        campo("Socio", lambda p: ttk.Combobox(p, textvariable=self.socio, values=socios))
        campo("Monto", lambda p: ttk.Entry(p, textvariable=self.monto))
        campo("Concepto", lambda p: ttk.Entry(p, textvariable=self.concepto))

        ttk.Label(marco, text="Fecha en formato AAAA-MM-DD.  El concepto es la nota "
                              "que explica el movimiento (ej. «Pasajes», «Giro»).",
                  font=FONT_SMALL, bootstyle="secondary", wraplength=400).pack(
                      anchor=tk.W, pady=(10, 0))

        botones = ttk.Frame(marco)
        botones.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(botones, text="Guardar", command=self.guardar,
                   bootstyle="success").pack(side=tk.RIGHT, padx=4)
        ttk.Button(botones, text="Cancelar", command=self.window.destroy,
                   bootstyle="secondary").pack(side=tk.RIGHT)

    def guardar(self):
        fecha = self.fecha.get().strip()
        socio = self.socio.get().strip()
        texto = self.monto.get().strip().replace(".", "").replace(",", "")

        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha inválida", "Use el formato AAAA-MM-DD, por ejemplo 2026-08-17")
            return
        if not socio:
            messagebox.showerror("Falta el socio", "Escriba el nombre del socio")
            return
        try:
            monto = float(texto)
            if monto <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Monto inválido", "El monto debe ser un número mayor que cero")
            return

        conn = get_connection()
        try:
            guardar_giro(conn, self.giro_id, fecha, socio, monto,
                         self.concepto.get().strip(), self.tipo.get())
        finally:
            conn.close()

        self.window.destroy()
        self.al_guardar()
