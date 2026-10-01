# ---------- Etapa 1: compilación ----------
# dlib (dependencia de face-recognition) se compila desde fuente y necesita
# cmake/g++/make + cabeceras de desarrollo. Esas herramientas solo hacen
# falta mientras se instalan las dependencias de Python, nunca en tiempo de
# ejecución: aislarlas en esta etapa evita que acaben en la imagen final.
FROM python:3.10-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        cmake \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Etapa 2: imagen final ----------
FROM python:3.10-slim

# Solo las librerías de SISTEMA necesarias en tiempo de ejecución por
# OpenCV y dlib (nada de compiladores): esto es lo que realmente reduce
# el tamaño final de la imagen en varios cientos de MB.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

# Paquetes Python ya compilados/instalados en la etapa anterior
COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

# Directorio donde se guardarán las plantillas biométricas (una por usuario)
RUN mkdir -p /app/data/usuarios && chown -R appuser:appuser /app

# Ejecutar como usuario sin privilegios (bastionado: si la app se ve
# comprometida, el atacante no obtiene una shell root dentro del contenedor).
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=3)" || exit 1

CMD ["python", "app.py"]
