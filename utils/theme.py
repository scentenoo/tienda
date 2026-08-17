"""Tema visual centralizado (ttkbootstrap, Flatly) para toda la app.

El tema se aplica una sola vez en main.py (ttkbootstrap.Window(themename="flatly")).
Este módulo solo define constantes de tipografía y widgets reutilizables para que
ninguna ventana tenga que volver a llamar ttk.Style()/theme_use() por su cuenta.
"""
import tkinter as tk
import ttkbootstrap as ttk

FONT_FAMILY = "Segoe UI"
FONT_SMALL = (FONT_FAMILY, 9)
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_HEADER = (FONT_FAMILY, 13, "bold")
FONT_TITLE = (FONT_FAMILY, 20, "bold")

# Colores para filas de Treeview (tag_configure) que necesitan resaltar un estado.
# Coherentes con los roles success/warning/danger/info del tema Flatly.
ROW_COLORS = {
    "success": {"background": "#d4edda", "foreground": "#18763b"},
    "warning": {"background": "#fff3cd", "foreground": "#9c6f11"},
    "danger": {"background": "#f8d7da", "foreground": "#a3242f"},
    "info": {"background": "#d6eaf8", "foreground": "#1f618d"},
}


def header_bar(parent, title, on_logout=None, logout_text="Cerrar Sesión"):
    """Barra oscura superior con título y, opcionalmente, botón de acción a la derecha."""
    bar = ttk.Frame(parent, bootstyle="dark")
    bar.pack(fill=tk.X)
    ttk.Label(bar, text=title, font=FONT_HEADER, bootstyle="inverse-dark").pack(
        side=tk.LEFT, padx=20, pady=12
    )
    if on_logout:
        ttk.Button(
            bar, text=logout_text, command=on_logout, bootstyle="danger-outline"
        ).pack(side=tk.RIGHT, padx=20, pady=10)
    return bar


def kpi_card(parent, label, value, bootstyle="secondary"):
    """Tarjeta compacta para una métrica (caja del día, resúmenes, etc.).

    Devuelve (card, value_label) para que el llamador pueda actualizar el
    valor mostrado más adelante con value_label.config(text=...).
    """
    card = ttk.Frame(parent, bootstyle=bootstyle, padding=12)
    ttk.Label(card, text=label, font=FONT_SMALL, bootstyle=f"inverse-{bootstyle}").pack(
        anchor=tk.W
    )
    value_label = ttk.Label(card, text=value, font=FONT_HEADER, bootstyle=f"inverse-{bootstyle}")
    value_label.pack(anchor=tk.W)
    return card, value_label


def role_color(role):
    """Devuelve el hex de un rol del tema activo (primary, success, danger, etc.).

    Útil para tag_configure() de Treeview, que no entiende bootstyle.
    """
    return ttk.Style().colors.get(role)
