# Página del celular (web/), para Google Cloud Run.
# La app de escritorio no se empaqueta aquí; ver build_windows.ps1.
FROM python:3.13-slim

# tzdata: para que "hoy" y la hora de las ventas sean las de Colombia
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*
ENV TZ=America/Bogota \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

# Solo lo que usa la página: nada de datos ni de la app de escritorio
COPY config/__init__.py config/nube.py config/
COPY utils/__init__.py utils/conciliacion.py utils/pdf.py utils/estado_cuenta.py utils/informe_movil.py utils/
COPY servicios/ servicios/
COPY web/ web/

# Un solo proceso: la protección contra intentos de contraseña vive en memoria
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 web.app:app
