FROM python:3.10-slim

# Dependencias del sistema para compilar dlib/OpenCV sin interfaz gráfica
RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    make \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Directorio donde se guardará la biometría persistente
RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python", "app.py"]