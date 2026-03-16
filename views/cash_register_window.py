import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from models.cash_register import CashRegister
from utils.formatters import format_currency


class CashRegisterWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user

        self.window = tk.Toplevel(parent)
        self.window.title("💵 Caja del Día")
        self.window.geometry("860x620")
        self.window.resizable(True, True)

        self._selected_date = date.today().isoformat()

        self._setup_styles()
        self._setup_ui()
        self._load_day(self._selected_date)

    # ─────────────────────────────────────────────────────────────
    # ESTILOS
    # ─────────────────────────────────────────────────────────────
    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#f8f9fa')
        self.style.configure('TLabel', background='#f8f9fa')
        self.style.configure('TNotebook', background='#f8f9fa')
        self.style.configure('TNotebook.Tab', font=('Arial', 10, 'bold'), padding=(12, 6))
        self.style.configure('Header.TLabel',
                              font=('Arial', 22, 'bold'),
                              foreground='#2e7d32',
                              background='#f8f9fa')
        self.style.configure('Sub.TLabel',
                              font=('Arial', 11),
                              foreground='#555',
                              background='#f8f9fa')
        self.style.configure('Accent.TButton',
                              font=('Arial', 10, 'bold'),
                              foreground='white',
                              background='#4a6baf')
        self.style.configure('Treeview', rowheight=26, font=('Arial', 9))
        self.style.configure('Treeview.Heading', font=('Arial', 9, 'bold'))

    # ─────────────────────────────────────────────────────────────
    # LAYOUT PRINCIPAL
    # ─────────────────────────────────────────────────────────────
    def _setup_ui(self):
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Pestaña 1: Caja del día
        self.day_frame = ttk.Frame(notebook, padding=10)
        notebook.add(self.day_frame, text='  Caja del Día  ')

        # Pestaña 2: Historial
        self.hist_frame = ttk.Frame(notebook, padding=10)
        notebook.add(self.hist_frame, text='  Historial  ')

        self._build_day_tab()
        self._build_history_tab()

        notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    # ─────────────────────────────────────────────────────────────
    # PESTAÑA: CAJA DEL DÍA
    # ─────────────────────────────────────────────────────────────
    def _build_day_tab(self):
        frame = self.day_frame

        # ── Selector de fecha ──────────────────────────────────
        date_row = ttk.Frame(frame)
        date_row.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(date_row, text='◀ Día anterior',
                   command=self._prev_day,
                   style='Accent.TButton').pack(side=tk.LEFT)

        self.date_label = ttk.Label(date_row,
                                    text=self._selected_date,
                                    font=('Arial', 12, 'bold'),
                                    foreground='#343a40',
                                    background='#f8f9fa')
        self.date_label.pack(side=tk.LEFT, padx=15)

        ttk.Button(date_row, text='Día siguiente ▶',
                   command=self._next_day,
                   style='Accent.TButton').pack(side=tk.LEFT)

        ttk.Button(date_row, text='🔄 Hoy',
                   command=self._go_today,
                   style='Accent.TButton').pack(side=tk.LEFT, padx=(15, 0))

        ttk.Button(date_row, text='↺ Actualizar',
                   command=lambda: self._load_day(self._selected_date)).pack(side=tk.RIGHT)

        # ── Totales del día ────────────────────────────────────
        totals_frame = ttk.Frame(frame)
        totals_frame.pack(fill=tk.X, pady=(0, 12))

        # Tarjeta: Ventas contado
        card1 = tk.Frame(totals_frame, bg='#e8f5e9', bd=1, relief='solid')
        card1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ttk.Label(card1, text='Ventas al contado',
                  font=('Arial', 9), foreground='#555',
                  background='#e8f5e9').pack(pady=(8, 0))
        self.lbl_contado = tk.Label(card1, text='$0',
                                    font=('Arial', 16, 'bold'),
                                    fg='#2e7d32', bg='#e8f5e9')
        self.lbl_contado.pack(pady=(0, 8))

        # Tarjeta: Abonos
        card2 = tk.Frame(totals_frame, bg='#e3f2fd', bd=1, relief='solid')
        card2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ttk.Label(card2, text='Abonos de clientes',
                  font=('Arial', 9), foreground='#555',
                  background='#e3f2fd').pack(pady=(8, 0))
        self.lbl_abonos = tk.Label(card2, text='$0',
                                   font=('Arial', 16, 'bold'),
                                   fg='#1565c0', bg='#e3f2fd')
        self.lbl_abonos.pack(pady=(0, 8))

        # Tarjeta: Total general
        card3 = tk.Frame(totals_frame, bg='#343a40', bd=1, relief='solid')
        card3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(card3, text='TOTAL EN CAJA',
                  font=('Arial', 9, 'bold'), foreground='#aaa',
                  background='#343a40').pack(pady=(8, 0))
        self.lbl_total = tk.Label(card3, text='$0',
                                  font=('Arial', 18, 'bold'),
                                  fg='white', bg='#343a40')
        self.lbl_total.pack(pady=(0, 8))

        # ── Listado de movimientos ─────────────────────────────
        list_frame = ttk.LabelFrame(frame, text=' Movimientos del día ', padding=6)
        list_frame.pack(fill=tk.BOTH, expand=True)

        cols = ('Hora', 'Tipo', 'Descripción', 'Monto')
        self.mov_tree = ttk.Treeview(list_frame, columns=cols, show='headings')

        self.mov_tree.heading('Hora', text='Hora')
        self.mov_tree.heading('Tipo', text='Tipo')
        self.mov_tree.heading('Descripción', text='Descripción')
        self.mov_tree.heading('Monto', text='Monto')

        self.mov_tree.column('Hora', width=140, anchor=tk.CENTER)
        self.mov_tree.column('Tipo', width=130, anchor=tk.CENTER)
        self.mov_tree.column('Descripción', width=380, anchor=tk.W)
        self.mov_tree.column('Monto', width=110, anchor=tk.E)

        # Tags de color por tipo
        self.mov_tree.tag_configure('contado', foreground='#2e7d32')
        self.mov_tree.tag_configure('abono', foreground='#1565c0')

        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.mov_tree.yview)
        self.mov_tree.configure(yscrollcommand=sb.set)

        self.mov_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Etiqueta de "sin movimientos"
        self.lbl_empty = ttk.Label(frame,
                                   text='No hay movimientos para esta fecha.',
                                   font=('Arial', 10, 'italic'),
                                   foreground='#888',
                                   background='#f8f9fa')

    # ─────────────────────────────────────────────────────────────
    # PESTAÑA: HISTORIAL
    # ─────────────────────────────────────────────────────────────
    def _build_history_tab(self):
        frame = self.hist_frame

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(controls, text='Últimos días:',
                  font=('Arial', 10)).pack(side=tk.LEFT)

        self.days_var = tk.StringVar(value='30')
        days_combo = ttk.Combobox(controls, textvariable=self.days_var,
                                  values=['7', '15', '30', '60', '90'],
                                  width=5, state='readonly')
        days_combo.pack(side=tk.LEFT, padx=6)

        ttk.Button(controls, text='↺ Cargar historial',
                   command=self._load_history,
                   style='Accent.TButton').pack(side=tk.LEFT)

        # Treeview historial
        cols = ('Fecha', 'Ventas contado', 'Abonos', 'Total en caja')
        self.hist_tree = ttk.Treeview(frame, columns=cols, show='headings')

        for col in cols:
            self.hist_tree.heading(col, text=col)

        self.hist_tree.column('Fecha', width=120, anchor=tk.CENTER)
        self.hist_tree.column('Ventas contado', width=160, anchor=tk.E)
        self.hist_tree.column('Abonos', width=160, anchor=tk.E)
        self.hist_tree.column('Total en caja', width=160, anchor=tk.E)

        self.hist_tree.tag_configure('alt', background='#f0f4ff')

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=sb.set)

        self.hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Doble clic en historial → ir al día
        self.hist_tree.bind('<Double-1>', self._on_history_click)

        self._load_history()

    # ─────────────────────────────────────────────────────────────
    # CARGA DE DATOS
    # ─────────────────────────────────────────────────────────────
    def _load_day(self, date_str):
        self._selected_date = date_str
        self.date_label.config(text=date_str)

        summary = CashRegister.get_daily_summary(date_str)
        movements = CashRegister.get_movements_by_date(date_str)

        # Actualizar tarjetas
        self.lbl_contado.config(text=format_currency(summary['total_contado']))
        self.lbl_abonos.config(text=format_currency(summary['total_abonos']))
        self.lbl_total.config(text=format_currency(summary['total_general']))

        # Actualizar lista
        for row in self.mov_tree.get_children():
            self.mov_tree.delete(row)

        if not movements:
            self.lbl_empty.pack(pady=4)
        else:
            self.lbl_empty.pack_forget()
            for m in movements:
                hora = m['hora']
                # Mostrar solo HH:MM:SS si la hora incluye fecha
                if 'T' in hora or ' ' in hora:
                    hora = hora.split('T')[-1].split(' ')[-1][:8]

                tag = 'contado' if m['tipo'] == 'Venta contado' else 'abono'
                self.mov_tree.insert('', tk.END, values=(
                    hora,
                    m['tipo'],
                    m['descripcion'],
                    format_currency(m['monto']),
                ), tags=(tag,))

    def _load_history(self):
        try:
            days = int(self.days_var.get())
        except ValueError:
            days = 30

        history = CashRegister.get_history(days)

        for row in self.hist_tree.get_children():
            self.hist_tree.delete(row)

        for i, entry in enumerate(history):
            tag = 'alt' if i % 2 == 0 else ''
            self.hist_tree.insert('', tk.END, values=(
                entry['fecha'],
                format_currency(entry['total_contado']),
                format_currency(entry['total_abonos']),
                format_currency(entry['total_general']),
            ), tags=(tag,))

    # ─────────────────────────────────────────────────────────────
    # NAVEGACIÓN DE FECHAS
    # ─────────────────────────────────────────────────────────────
    def _prev_day(self):
        d = date.fromisoformat(self._selected_date) - timedelta(days=1)
        self._load_day(d.isoformat())

    def _next_day(self):
        d = date.fromisoformat(self._selected_date) + timedelta(days=1)
        # No permitir navegar al futuro
        if d <= date.today():
            self._load_day(d.isoformat())

    def _go_today(self):
        self._load_day(date.today().isoformat())

    def _on_tab_changed(self, event):
        notebook = event.widget
        if notebook.index('current') == 1:  # Pestaña historial
            self._load_history()

    def _on_history_click(self, event):
        """Doble clic en historial: ir a ese día en la pestaña Caja del Día."""
        selected = self.hist_tree.selection()
        if not selected:
            return
        fecha = self.hist_tree.item(selected[0], 'values')[0]
        self._load_day(fecha)
        # Volver a la pestaña del día
        notebook = self.window.winfo_children()[0]
        if hasattr(notebook, 'select'):
            notebook.select(0)