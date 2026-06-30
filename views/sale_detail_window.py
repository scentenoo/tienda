import tkinter as tk
from tkinter import ttk, messagebox

from models.sale import Sale
from utils.formatters import format_number, format_currency
from config.database import get_connection


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

        sale = Sale.get_by_id(sale_id)
        if not sale:
            messagebox.showerror("Error", f"No se encontró la venta #{sale_id}")
            return

        self.sale = sale
        self._build_window()

    def _build_window(self):
        sale = self.sale

        self.window = tk.Toplevel(self.parent)
        self.window.title(f"Detalles de Venta #{sale.id}")
        self.window.geometry("600x500")
        self.window.resizable(True, True)
        self.window.transient(self.parent)
        self.window.grab_set()

        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Información general
        info_frame = ttk.LabelFrame(main_frame, text="Información General", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(info_frame, text=f"Venta ID: {sale.id}", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Fecha: {sale.created_at}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Cliente: {sale.client_name if sale.client_name else 'Venta al contado'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Estado: {'Pagado' if sale.status == 'paid' else 'Pendiente'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Tipo de Pago: {'Efectivo' if sale.payment_method == 'cash' else 'Crédito'}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Total: {format_currency(sale.total)}", font=("Arial", 12, "bold")).pack(anchor=tk.W)

        if hasattr(sale, 'adjustment') and sale.adjustment and sale.adjustment != 0:
            adjustment_text = "Ajuste: "
            if sale.adjustment > 0:
                adjustment_text += f"+${abs(sale.adjustment):,.2f}"
            else:
                adjustment_text += f"-${abs(sale.adjustment):,.2f}"

            ttk.Label(info_frame, text=adjustment_text,
                      foreground='orange' if sale.adjustment > 0 else 'green').pack(anchor=tk.W)

            if hasattr(sale, 'adjustment_reason') and sale.adjustment_reason:
                ttk.Label(info_frame, text=f"Razón: {sale.adjustment_reason}").pack(anchor=tk.W)

        # Productos
        products_frame = ttk.LabelFrame(main_frame, text="Productos Vendidos", padding=10)
        products_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        columns = ('Producto', 'Cantidad', 'Precio Unit.', 'Subtotal')
        details_tree = ttk.Treeview(products_frame, columns=columns, show='headings')

        for col in columns:
            details_tree.heading(col, text=col)
            if col == 'Cantidad':
                details_tree.column(col, width=100)
            elif col in ['Precio Unit.', 'Subtotal']:
                details_tree.column(col, width=120)
            else:
                details_tree.column(col, width=150)

        details_scrollbar = ttk.Scrollbar(products_frame, orient=tk.VERTICAL, command=details_tree.yview)
        details_tree.configure(yscrollcommand=details_scrollbar.set)

        details_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sd.*, p.name as product_name
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
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

        ttk.Button(main_frame, text="Cerrar", command=self.window.destroy).pack(pady=10)