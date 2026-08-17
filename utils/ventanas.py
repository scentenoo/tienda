"""Utilidades para ventanas de Tk."""


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
