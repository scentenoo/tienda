# Visitas al catálogo

Para saber qué hacen los clientes en el catálogo: quién entra, qué busca (y
no encuentra), qué agrega, si abre el pedido y si toca «Enviar por WhatsApp».
Se ve en la página del celular, en **Más → Visitas al catálogo**.

## Cómo funciona

1. **El catálogo** (`catalogo/plantilla.html`) junta lo que hace el cliente y
   lo manda cada 3 segundos y al salir, sin hacerlo esperar.
2. **El recibidor** (`visitas/worker.js`) corre en Cloudflare Workers, que no
   se duerme como Render. Revisa lo que llega y lo guarda en una **base de
   Turso aparte, solo de visitas**. No puede ver ni tocar ventas, clientes ni
   deudas.
3. **La página privada** (`web/visitas.py`) lee esa base con un token de solo
   lectura y le pone nombre a cada visita.

**¿Cómo sabe quién es?** El botón Enviar de *Domicilio* manda a cada cliente
su propio enlace con un código (`…/tienda/?c=k7m2q4xa`). El código sale del
número del cliente firmado con `SECRETO`: no dice el nombre y no se puede
adivinar el de otro. El teléfono lo recuerda, así que si después esa persona
entra desde un estado, se le sigue reconociendo. Quien entra sin código sale
como «sin nombre». Si alguien reenvía su enlace, lo que haga la otra persona
sale con su nombre. Si se cambia `SECRETO`, los enlaces ya enviados quedan
como visitas sin nombre.

Lo que se anota: entrada, categoría tocada, búsqueda (con cuántos
resultados), agregar, quitar, vaciar, ver pedido, enviar (con el total),
tocar «Escríbenos» y cuánto tiempo estuvo. Nada más: ni teléfono ni
dirección IP; el país sí, que lo pone Cloudflare.

## Ponerlo a andar (una sola vez)

### 1. La base de visitas, en Turso

En <https://app.turso.tech>:

1. **Create Database** → nombre `visitas`, el mismo grupo/región de la base
   de la tienda.
2. Copiar la dirección de la base (`libsql://visitas-<usuario>.turso.io`).
3. **Create Token** dos veces:
   - uno con **Full Access** → es para Cloudflare;
   - uno **Read Only** → es para Render.

No hace falta crear tablas: el recibidor las crea con la primera visita.

### 2. El recibidor, en Cloudflare

Desde esta carpeta, en el PC:

    cd visitas
    npx wrangler login                    (abre el navegador para entrar a Cloudflare)
    npx wrangler deploy
    npx wrangler secret put TURSO_URL     (pegar libsql://visitas-<usuario>.turso.io)
    npx wrangler secret put TURSO_TOKEN   (pegar el token Full Access)

`wrangler deploy` muestra la dirección del recibidor:
`https://visitas-hye.<su-subdominio>.workers.dev`. Si el catálogo se mueve a
otra dirección que no sea `https://scentenoo.github.io`, se cambia `ORIGEN`
en `wrangler.toml` y se vuelve a hacer `npx wrangler deploy`.

Para ver si está recibiendo (y los errores, si los hay):
`npx wrangler tail`.

### 3. El catálogo, en GitHub

Repositorio → Settings → *Secrets and variables → Actions → Variables* →
`VISITAS_URL` = la dirección del paso 2. Luego Actions → Catálogo → Run
workflow (o esperar la media hora). Sin esa variable, el catálogo no anota
nada.

### 4. La página privada, en Render

En las variables de entorno del servicio:

- `VISITAS_TURSO_URL` = `libsql://visitas-<usuario>.turso.io`
- `VISITAS_TURSO_TOKEN` = el token **Read Only**

## Probar

    python -m unittest pruebas.test_visitas     (la página y el resumen)
    node visitas/prueba.mjs                     (el recibidor)

Para ver el catálogo mandando avisos en el PC, se genera apuntando a un
recibidor local: `python -m catalogo.generar --db copia.db --whatsapp 3001234567
--visitas http://127.0.0.1:5078/ --salida sitio`.

## Límites

- El plan gratis de Cloudflare aguanta 100.000 avisos al día; el catálogo
  manda uno cada pocos segundos por persona mientras hace cosas.
- «Tocaron enviar» quiere decir que se les abrió WhatsApp con el pedido. Si
  de verdad lo mandaron, se ve en el chat.
- Cualquiera podría mandarle basura al recibidor. Solo llegaría a la base de
  visitas, y el recibidor revisa tipos y largos. Si pasa, se borra en Turso.
