# Respaldo en Google Drive desde la nube

Copia la base de Turso a Google Drive, en las mismas carpetas que el botón
"Guardar base de datos en Google Drive" del programa del computador:

- `Mi unidad/Emprendimiento/backups_db/tienda_backup_AAAA-MM-DD_HH-MM-SS.db`, uno por respaldo
- `Mi unidad/Emprendimiento/db_actual/tienda.db`, siempre el último

Se dejan los últimos 30 respaldos; los viejos van a la papelera de Drive.

Lo hace la tarea de GitHub `.github/workflows/respaldo.yml`:

- **sola, todas las noches** a las 11:43 p. m. (GitHub a veces se demora unos minutos);
- **cuando se toca «Respaldar en Google Drive»** en la pestaña Más de la página
  (solo la ve el dueño). En la misma tarjeta se ve cuándo fue el último y si falló.

Si un respaldo falla, GitHub manda un correo y la página lo muestra en rojo.

## Ponerlo en marcha (una sola vez, unos 10 minutos)

### 1. Un proyecto en Google Cloud (gratis)

1. Entrar a <https://console.cloud.google.com> con la cuenta dueña de la carpeta
   Emprendimiento y crear un proyecto nuevo, por ejemplo "Respaldo tienda".
2. **APIs y servicios → Biblioteca**: buscar **Google Drive API** y tocar **Habilitar**.
3. **Google Auth Platform** (o "Pantalla de consentimiento de OAuth"): tocar *Comenzar*,
   poner un nombre ("Respaldo tienda") y el correo, elegir el público (paso 4) y terminar.
4. Con una cuenta de organización (la de la universidad, @unal.edu.co) se elige
   **Interno** y no hay que publicar ni verificar nada. Con una cuenta personal
   (@gmail.com) sale **Externo**: entonces en **Público** hay que tocar **Publicar app**
   para que quede *En producción*; si se queda "en prueba", Google quita el permiso a
   los 7 días y el respaldo deja de funcionar.
5. En **Clientes** (o "Credenciales → Crear credenciales → ID de cliente de OAuth"):
   tipo **App de escritorio**, crearlo y copiar el **ID de cliente** y el **secreto**.

### 2. Dar el permiso (en el computador)

En la carpeta del proyecto:

    python -m respaldo.autorizar ID_DE_CLIENTE SECRETO

Se abre Google: entrar con la misma cuenta (si es «Interno» y se entra con otra,
Google dice "Error de autorización"). Va a decir **"Google no verificó esta app"**,
que es normal porque la app es suya: tocar *Configuración avanzada → Ir a Respaldo tienda*
y luego **Continuar/Permitir**. La terminal muestra si ve la carpeta Emprendimiento e
imprime el **refresh token**.

Ese token permite entrar al Drive de la cuenta: va solo en GitHub, no se manda a nadie.

### 3. Las claves en GitHub

En el repositorio: **Settings → Secrets and variables → Actions**.

Pestaña **Secrets** (*New repository secret*):

| Nombre                   | Valor                         |
|--------------------------|-------------------------------|
| `GOOGLE_CLIENTE_ID`      | el ID de cliente del paso 1   |
| `GOOGLE_CLIENTE_SECRETO` | el secreto del paso 1         |
| `GOOGLE_REFRESH_TOKEN`   | lo que imprimió el paso 2     |

`TURSO_URL` y `TURSO_TOKEN` ya están, porque los usan los avisos.

Pestaña **Variables** (*New repository variable*): `RESPALDO_CARPETA` = `Emprendimiento`.
Mientras no exista esta variable, la tarea no hace nada.

### 4. Probarlo

En GitHub: **Actions → Respaldo → Run workflow**. En un par de minutos debe aparecer el
archivo nuevo en `Emprendimiento/backups_db` de Drive.

El botón de la página usa el mismo token de GitHub que «Actualizar el catálogo»
(`CATALOGO_REPO` y `CATALOGO_TOKEN` en Render). Si ese botón ya aparece en Más,
el del respaldo también aparece.

## Si algo falla

- **"Google ya no acepta el permiso"**: se revocó el permiso o la app quedó "en prueba".
  Revisar el paso 1.4 y repetir el paso 2 (el token nuevo reemplaza `GOOGLE_REFRESH_TOKEN`).
- **"Falta la variable …"**: falta un secreto del paso 3.
- Probar sin subir nada, con las mismas variables puestas en la terminal:
  `python -m respaldo.respaldar --probar`
- GitHub apaga las tareas automáticas de un repositorio público que lleva 60 días sin
  cambios. Si pasa, avisa por correo; se vuelven a activar en **Actions → Respaldo**.
