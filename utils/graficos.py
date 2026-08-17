"""Utilidades para que los gráficos del panel sean legibles e interactivos.

Los gráficos planos de matplotlib no dicen nada por sí solos: el eje sale en
notación científica (1e6) y no hay forma de saber a qué corresponde cada barra.
Aquí se resuelven las tres cosas: escala legible, el valor escrito encima, y
una etiqueta flotante al pasar el ratón.
"""
from matplotlib.ticker import FuncFormatter


def formato_corto(valor, _=None):
    """1_950_000 → '1,95 M'   ·   250_000 → '250 k'"""
    v = abs(valor)
    signo = "-" if valor < 0 else ""
    if v >= 1_000_000:
        return f"{signo}{v / 1_000_000:,.2f} M".replace(".", ",")
    if v >= 1_000:
        return f"{signo}{v / 1_000:,.0f} k"
    return f"{signo}{v:,.0f}"


def formato_pesos(valor):
    """1950000 → '$1.950.000'   ·   -96625 → '-$96.625'"""
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,.0f}".replace(",", ".")


def escala_legible(ax, eje="x"):
    """Cambia 1e6 por '1,00 M' en el eje indicado."""
    formateador = FuncFormatter(formato_corto)
    if eje in ("x", "ambos"):
        ax.xaxis.set_major_formatter(formateador)
    if eje in ("y", "ambos"):
        ax.yaxis.set_major_formatter(formateador)


class Interactivo:
    """Etiqueta flotante que sigue al ratón sobre barras, puntos y porciones.

    Se registra cada elemento con el texto que debe mostrar; al pasar por
    encima aparece una nota con el dato exacto, y al hacer clic se envía a
    la función `al_hacer_clic` si se indicó una.
    """

    def __init__(self, figura, canvas, al_hacer_clic=None):
        self.figura = figura
        self.canvas = canvas
        self.al_hacer_clic = al_hacer_clic
        self.elementos = []          # (artist, texto, ax)
        self.notas = {}              # ax → annotation
        canvas.mpl_connect("motion_notify_event", self._mover)
        canvas.mpl_connect("button_press_event", self._clic)

    def _nota(self, ax):
        if ax not in self.notas:
            nota = ax.annotate(
                "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.5", fc="#2c3e50", ec="none", alpha=0.95),
                color="white", fontsize=8, zorder=100, annotation_clip=False)
            nota.set_visible(False)
            self.notas[ax] = nota
        return self.notas[ax]

    def registrar(self, artist, texto, ax):
        self.elementos.append((artist, texto, ax))

    def _buscar(self, evento):
        for artist, texto, ax in self.elementos:
            if ax is not evento.inaxes:
                continue
            try:
                dentro, _ = artist.contains(evento)
            except Exception:
                continue
            if dentro:
                return artist, texto, ax
        return None

    def _mover(self, evento):
        encontrado = self._buscar(evento) if evento.inaxes else None
        cambio = False
        for ax, nota in self.notas.items():
            if nota.get_visible() and (not encontrado or encontrado[2] is not ax):
                nota.set_visible(False)
                cambio = True
        if encontrado:
            _, texto, ax = encontrado
            nota = self._nota(ax)
            nota.xy = (evento.xdata, evento.ydata)
            nota.set_text(texto)
            nota.set_visible(True)
            cambio = True
        if cambio:
            self.canvas.draw_idle()

    def _clic(self, evento):
        encontrado = self._buscar(evento) if evento.inaxes else None
        if encontrado and self.al_hacer_clic:
            self.al_hacer_clic(encontrado[1])
