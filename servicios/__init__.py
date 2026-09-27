"""Operaciones que escriben en la base, compartidas por la aplicación de
escritorio y la página del celular, para que las dos hagan exactamente lo
mismo.

Con la base en la nube cada instrucción que escribe es un viaje a internet
(~0,2 s), así que aquí se agrupan: varias filas por INSERT, un solo UPDATE con
CASE para varios productos, y un solo commit por operación.

Ninguna función abre ni cierra la conexión, ni hace commit: la recibe y el
que llama decide.
"""
