"""Utilidades para ventanas de Tk."""


def centrar_ventana(ventana, ancho, alto, margen_alto=70):
    """Centra la ventana con un tamaño que no se salga de la pantalla.

    Los tamaños fijos de cada ventana se pensaron en un monitor grande;
    en portátiles con menos resolución o con escalado de Windows, el alto
    pedido no cabe entre el borde de arriba y la barra de tareas, y la
    ventana queda con botones fuera de la vista sin que el usuario pueda
    hacer nada (algunas ventanas no son redimensionables). margen_alto
    reserva espacio para la barra de título y la barra de tareas.
    """
    ventana.update_idletasks()
    pantalla_ancho = ventana.winfo_screenwidth()
    pantalla_alto = ventana.winfo_screenheight()

    ancho = min(ancho, pantalla_ancho - 40)
    alto = min(alto, pantalla_alto - margen_alto)

    x = max((pantalla_ancho - ancho) // 2, 0)
    y = max((pantalla_alto - alto) // 2, 0)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def hacer_modal(ventana, padre=None, intentos=20):
    """Hace modal una ventana recién creada, sin bloquear nunca.

    En Linux, grab_set() lanza 'grab failed: window not viewable' si la
    ventana todavía no está mapeada en pantalla. En Windows funciona igual,
    por eso este fallo no aparecía cuando la aplicación corría allá: la
    excepción abortaba el dibujado y dejaba la ventana en blanco.

    Esperar con wait_visibility() lo resolvía, pero se queda colgado para
    siempre si el padre está oculto. Por eso aquí se reintenta con after(),
    que devuelve el control de inmediato: si la ventana llega a ser visible
    el grab entra, y si no, simplemente se queda sin ser modal.
    """
    if padre is not None:
        try:
            ventana.transient(padre)
        except Exception:
            pass

    ventana.update_idletasks()

    def intentar(restantes):
        try:
            ventana.grab_set()
        except Exception:
            try:
                if restantes > 0 and ventana.winfo_exists():
                    ventana.after(50, lambda: intentar(restantes - 1))
            except Exception:
                pass  # la ventana se cerró mientras esperábamos

    intentar(intentos)
