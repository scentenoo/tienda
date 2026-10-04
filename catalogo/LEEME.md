# Catálogo para clientes

Una página pública con los productos, sus precios y si hay o van por encargo.
El cliente arma el pedido y lo manda por WhatsApp. Sale de la misma base de
la tienda: lo que se cambia en la app es lo que aparece.

No vive en Render: se publica en GitHub Pages, aparte de la página de ventas.
Si el catálogo se cae, las ventas siguen; y el enlace que circula por los
estados no lleva a la pantalla de la contraseña.

## Qué se ve y qué no

Cada producto tiene dos datos nuevos, en el formulario de producto (en el
celular y en el PC):

- **Categoría**: en qué sección sale. Sin categoría, sale en «Otros».
- **¿Aparece en el catálogo?**
  - *Automático*: aparece si hay stock; agotado, sale como «Por encargo»
    mientras se haya comprado en los últimos 2 meses; después se oculta solo.
  - *Siempre*: aparece aunque lleve mucho agotado (lo que solo se trae bajo pedido).
  - *Nunca*: no aparece aunque haya stock.

La regla está en `servicios/catalogo.py` (ahí se cambian los 2 meses, las
categorías y desde cuántas unidades dice «Últimas unidades»). Al cliente
nunca le llega el costo ni la cantidad exacta en stock.

Ojo: la regla de los 2 meses mira las **compras registradas**. Si el stock de
un producto se sube a mano sin registrar la compra, cuando se agote se oculta
de una vez en lugar de salir como «Por encargo».

## Ponerlo a andar (una sola vez)

1. **Preparar la base.** Agrega las dos columnas y le pone categoría a los
   productos que ya existen. Primero muestra lo que haría; con `--aplicar` lo hace:

       python herramientas/preparar_catalogo.py dist/CharcuteriaHYE/data/nube.json
       python herramientas/preparar_catalogo.py dist/CharcuteriaHYE/data/nube.json --aplicar

2. **Crear un token de solo lectura** para la base (el catálogo no debe poder
   escribir):

       turso db tokens create <nombre-de-la-base> --read-only

3. **En GitHub**, en el repositorio → Settings:
   - *Secrets and variables → Actions → Secrets*: `TURSO_URL` y
     `TURSO_TOKEN_LECTURA` (el del paso 2).
   - *Pages → Build and deployment → Source*: **GitHub Actions**.
   - *Secrets and variables → Actions → Variables*: `WHATSAPP_NEGOCIO`, el
     número al que llegan los pedidos (10 dígitos). Esta se pone de última:
     mientras no exista, la tarea del catálogo no hace nada.

4. **Lanzarlo la primera vez**: pestaña Actions → Catálogo → Run workflow.
   Al terminar muestra la dirección del catálogo
   (`https://<usuario>.github.io/<repositorio>/`).

Desde ahí se actualiza solo cada media hora. Si un día falla (por ejemplo, se
venció el token), GitHub manda un correo y el catálogo se queda con lo último
que se publicó: la línea «Actualizado…» de arriba cambia de color cuando lleva
más de 3 horas sin actualizarse.

GitHub apaga las tareas programadas de un repositorio que pasa 60 días sin
ningún cambio. Si eso pasa, se vuelve a encender en la pestaña Actions.

## Que se actualice al instante (opcional)

Para que un cambio de precio no espere la media hora, la página del celular
puede avisarle a GitHub. En Render se agregan dos variables:

- `CATALOGO_REPO`: `usuario/repositorio`
- `CATALOGO_TOKEN`: un token de GitHub *fine-grained*, solo para este
  repositorio, con los permisos **Actions: Read and write** (este aviso) y
  **Contents: Read and write** (las fotos, abajo), y ningún otro.

Sin esas variables no hace nada. Solo avisa al crear, editar o borrar un
producto; el stock que baja con las ventas se refleja en la siguiente media hora.

## Fotos

Se ponen desde el formulario de producto de la página del celular, en
«Foto para el catálogo»: se toma o se elige la foto y listo. El teléfono la
recorta en 4:3 y la achica (unos 100 KB); la página la guarda en GitHub, en
`catalogo/fotos/<id>.jpg`, y ese cambio publica el catálogo solo, en un par de
minutos. Ahí mismo se cambia o se quita.

Necesita las dos variables de Render de arriba (sin ellas, la sección no
aparece). Y como cada foto es un cambio en el repositorio, en Render conviene
poner en *Settings → Build Filters → Ignored Paths* la ruta `catalogo/fotos/**`,
para que subir una foto no vuelva a desplegar la página de ventas.

Mientras no haya ninguna foto, las tarjetas salen sin recuadro; con la
primera, las que no tengan salen con la inicial del producto.

Quien trabaje en el repositorio desde el PC tiene que hacer `git pull` antes
de subir cambios, porque las fotos llegan a GitHub directamente.

## Probarlo en el PC

    python -m catalogo.generar --db copia.db --whatsapp 3001234567 --salida sitio

y se abre `sitio/index.html`. Las pruebas: `python -m unittest pruebas.test_catalogo`.
