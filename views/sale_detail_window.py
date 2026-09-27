import tkinter as tk
from tkinter import messagebox
from types import SimpleNamespace

import ttkbootstrap as ttk

from models.sale import Sale
from utils.formatters import format_number, format_currency
from utils.theme import FONT_HEADER
from config.database import get_connection
from utils.ventanas import hacer_modal, centrar_ventana


class SaleDetailWindow:
    """
    Ventana reutilizable para mostrar el detalle completo de una venta
    (información general + productos vendidos).

    Se usa tanto desde 'Lista de Ventas' como desde el 'Historial de
    Transacciones' de un cliente, para no tener que ir a buscar la venta
    manualmente en otra pantalla.
    """

    def __init__(self, parent, sale_id):
        self.parent = parent
        self.sale_id = sale_id
        self.eliminada = False

        sale = Sale.get_by_id(sale_id)
        if not sale:
            # La venta pudo haberse eliminado. Al eliminarla se archiva con sus
            # líneas, así que el historial del cliente todavía puede mostrarla.
            sale = self._buscar_en_archivo(sale_id)
            self.eliminada = sale is not None

        if not sale:
            messagebox.showinfo(
                "Venta no disponible",
                f"La venta #{sale_id} fue eliminada antes de que la aplicación "
                f"empezara a archivarlas, así que su detalle ya no existe.\n\n"
                f"La transacción sigue en el historial del cliente como registro "
                f"del movimiento de dinero."
            )
            return

        self.sale = sale
        self._build_window()

    def _buscar_en_archivo(self, sale_id):
        """Recupera una venta eliminada desde las tablas de archivo."""
        try:
            conn = get_connection()
            row = conn.execute('''
                SELECT se.*, c.name AS client_name
                  FROM sales_eliminadas se
                  LEFT JOIN clients c ON c.id = se.client_id
                 WHERE se.id = ?
            ''', (sale_id,)).fetchone()
            conn.close()
        except Exception:
            return None

        if not row:
            return None

        return SimpleNamespace(
            id=row['id'],
            client_id=row['client_id'],
            client_name=row['client_name'],
            total=row['total'],
            payment_method=row['payment_method'],
            notes=row['notes'],
            created_at=row['created_at'],
            status=row['status'],
            adjustment=row['adjustment'],
            adjustment_reason=row['adjustment_reason'],
            eliminada_en=row['eliminada_en'],
        )

    def _build_window(self):
        sale = self.sale

        self.window = tk.Toplevel(self.parent)
        titulo = f"Detalles de Venta #{sale.id}"
        if self.eliminada:
            titulo += "  (eliminada)"
        self.window.title(titulo)
        self.window.resizable(True, True)
        self.window.transient(self.parent)
        hacer_modal(self.window)
        centrar_ventana(self.window, 600, 500)
        self.window.minsize(500, 420)

        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        if self.eliminada:
            ttk.Label(
                main_frame,
                text=f"⚠  Esta venta fue eliminada el {sale.eliminada_en}. "
                     f"Se muestra desde el archivo.",
                bootstyle="warning",
                wraplength=540,
            ).pack(anchor=tk.W, pady=(0, 10))

        # Información general
        info_frame = ttk.LabelFrame(main_frame, text="Información General", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(info_frame, text=f"Venta ID: {sale.id}", font=FONT_HEADER).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Fecha: {sale.created_at}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Cliente: {sale.client_name if sale.client_name else 'Venta al contado'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Estado: {'Pagado' if sale.status == 'paid' else 'Pendiente'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Tipo de Pago: {'Efectivo' if sale.payment_method == 'cash' else 'Crédito'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Total: {format_currency(sale.total)}", font=FONT_HEADER).pack(anchor=tk.W)

        if hasattr(sale, 'adjustment') and sale.adjustment and sale.adjustment != 0:
            adjustment_text = "Ajuste: "
            if sale.adjustment > 0:
                adjustment_text += f"+${abs(sale.adjustment):,.2f}"
            else:
                adjustment_text += f"-${abs(sale.adjustment):,.2f}"

            ttk.Label(info_frame, text=adjustment_text,
                      bootstyle='warning' if sale.adjustment > 0 else 'success').pack(anchor=tk.W)

            if hasattr(sale, 'adjustment_reason') and sale.adjustment_reason:
                ttk.Label(info_frame, text=f"Razón: {sale.adjustment_reason}").pack(anchor=tk.W)

        # Productos
        products_frame = ttk.LabelFrame(main_frame, text="Productos Vendidos", padding=10)
        products_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        details_table_frame = ttk.Frame(products_frame)
        details_table_frame.pack(fill=tk.BOTH, expand=True)
        details_table_frame.rowconfigure(0, weight=1)
        details_table_frame.columnconfigure(0, weight=1)

        columns = ('Producto', 'Cantidad', 'Precio Unit.', 'Subtotal')
        details_tree = ttk.Treeview(details_table_frame, columns=columns, show='headings')

        col_config = {
            'Producto': (150, 110, 'w'),
            'Cantidad': (100, 80, 'e'),
            'Precio Unit.': (120, 90, 'e'),
            'Subtotal': (120, 90, 'e'),
        }
        for col in columns:
            details_tree.heading(col, text=col)
            width, minwidth, anchor = col_config[col]
            details_tree.column(col, width=width, minwidth=minwidth, anchor=anchor)

        details_vsb = ttk.Scrollbar(details_table_frame, orient=tk.VERTICAL, command=details_tree.yview)
        details_hsb = ttk.Scrollbar(details_table_frame, orient=tk.HORIZONTAL, command=details_tree.xview)
        details_tree.configure(yscrollcommand=details_vsb.set, xscrollcommand=details_hsb.set)

        details_tree.grid(row=0, column=0, sticky="nsew")
        details_vsb.grid(row=0, column=1, sticky="ns")
        details_hsb.grid(row=1, column=0, sticky="ew")

        try:
            conn = get_connection()
            cursor = conn.cursor()
            if self.eliminada:
                cursor.execute('''
                    SELECT sd.*, COALESCE(sd.product_name, p.name) AS product_name
                      FROM sale_details_eliminados sd
                      LEFT JOIN products p ON p.id = sd.product_id
                     WHERE sd.sale_id = ?
                ''', (sale.id,))
            else:
                # LEFT JOIN para no perder líneas si el producto fue borrado
                cursor.execute('''
                    SELECT sd.*, COALESCE(p.name, '(producto eliminado)') AS product_name
                      FROM sale_details sd
                      LEFT JOIN products p ON sd.product_id = p.id
                     WHERE sd.sale_id = ?
                ''', (sale.id,))

            details = cursor.fetchall()
            conn.close()

            for detail in details:
                details_tree.insert('', tk.END, values=(
                    detail['product_name'],
                    format_number(detail['quantity']),
                    format_currency(detail['unit_price']),
                    format_currency(detail['subtotal'])
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar productos de la venta:\n{str(e)}")

        ttk.Button(main_frame, text="Cerrar", command=self.window.destroy, bootstyle="secondary").pack(pady=10)