# Avisos al celular

Notificaciones como las de cualquier app, aunque la página esté cerrada:

| Cuándo | Aviso |
|---|---|
| Martes (mañana y tarde) y miércoles, si no se ha contado | Hoy toca el conteo |
| Martes a jueves, ya contado, si no se ha pedido | Hay que pedir a Cúcuta (si pasa de $200.000 o algo se acaba antes) |
| Martes tarde / miércoles mañana, si no hay día de viaje | ¿Qué día bajan a Medellín? |
| El día antes del viaje y el mismo día | Hay que hacer el pedido de Medellín |
| Domingo en la mañana | Hoy se compra el queso: unos N kg |
| Cada mañana, si un pedido ya debía haber llegado | ¿Ya llegó el pedido? |

La regla está en `utils/reposicion.py` (`avisos_de_hoy`). Los manda
`avisos/enviar.py`, que corre en GitHub dos veces al día
(`.github/workflows/avisos.yml`). Cada aviso se manda una sola vez.

## Ponerlos en marcha (una sola vez)

1. **Crear las claves** en el PC, dentro del repositorio:

   ```
   uv pip install cryptography
   python -m avisos.claves
   ```

   Salen dos líneas: `VAPID_PUBLICA` y `VAPID_PRIVADA`. La privada no se
   comparte ni se sube al repositorio (es público).

2. **En GitHub**: el repositorio → *Settings → Secrets and variables → Actions*.
   - Pestaña *Secrets*:
     - `VAPID_PRIVADA`: la privada.
     - `TURSO_TOKEN`: el mismo token que usa la página. Este sí escribe:
       anota qué avisos ya se mandaron y quita los celulares que ya no
       reciben. `TURSO_URL` ya existe, porque la usa el catálogo.
   - Pestaña *Variables*: `VAPID_PUBLICA` con la pública. Mientras esta
     variable no exista, la tarea no hace nada.

3. **En el servidor de la página** (Render o Cloud Run): agregar la
   variable de entorno `VAPID_PUBLICA` con la misma clave pública y volver
   a desplegar.

4. **En cada celular**: *Más → Avisos en este celular → Activar avisos* y
   tocar *Permitir*.
   - **Android**: desde Chrome, o desde el ícono instalado.
   - **iPhone** (iOS 16.4 o más nuevo): primero *Compartir → Agregar a
     inicio*, abrir la página desde ese ícono y ahí activar. Desde Safari
     normal no deja.

5. **Probar**: en esa misma pantalla, *Mandar un aviso de prueba a todos*.
   Funciona si la página tiene `CATALOGO_REPO` y `CATALOGO_TOKEN`, el mismo
   token que actualiza el catálogo, con permiso *Actions: Read and write*.
   Si no, en GitHub: *Actions → Avisos → Run workflow* con `prueba` = `si`.

Para ver qué avisos tocarían ahora sin mandar nada:

```
python -m avisos.enviar --ver
```

Si se cambian las claves, cada celular tiene que volver a activar los avisos.
