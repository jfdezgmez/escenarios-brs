import base64
import logging
import os
from pathlib import Path

import cv2
import face_recognition
import numpy as np
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
# Un frame JPEG de cámara a resolución razonable no debería superar esto.
# Limitarlo evita que una petición maliciosa o defectuosa intente colar
# un payload enorme y agote memoria/CPU del contenedor.
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
USUARIOS_DIR = DATA_DIR / "usuarios"
USUARIOS_DIR.mkdir(parents=True, exist_ok=True)

# --- Umbrales configurables por variable de entorno ---
EAR_UMBRAL = float(os.environ.get("EAR_UMBRAL", 0.21))
UMBRAL_DISTANCIA = float(os.environ.get("UMBRAL_DISTANCIA", 0.50))
PARPADEOS_REQUERIDOS = int(os.environ.get("PARPADEOS_REQUERIDOS", 2))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("biometria")


def ruta_usuario(nombre):
    """Convierte un nombre de usuario en una ruta segura dentro de USUARIOS_DIR.

    Se restringe a alfanuméricos, guiones y guiones bajos para evitar
    cualquier intento de path traversal (p. ej. nombre="../../etc/passwd").
    """
    if not nombre:
        return None
    # Restringido a ASCII a propósito (no solo "isalnum()", que también
    # aceptaría letras acentuadas/unicode): evita problemas de
    # normalización de nombres de fichero entre distintos sistemas de
    # archivos (Linux/macOS/Windows) cuando ./data se monta como volumen.
    nombre_seguro = "".join(
        c for c in nombre.strip().lower() if (c.isascii() and c.isalnum()) or c in ("-", "_")
    )
    if not nombre_seguro:
        return None
    return USUARIOS_DIR / f"{nombre_seguro}.npy"


def listar_usuarios():
    return sorted(p.stem for p in USUARIOS_DIR.glob("*.npy"))


def base64_to_cv2(base64_string):
    if not isinstance(base64_string, str):
        raise ValueError("El campo 'image' debe ser una cadena en base64.")
    if "," in base64_string:
        base64_string = base64_string.split(",", 1)[1]
    try:
        datos = base64.b64decode(base64_string)
    except (base64.binascii.Error, ValueError) as exc:
        raise ValueError("La imagen recibida no es un base64 válido.") from exc

    nparr = np.frombuffer(datos, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("No se pudo decodificar la imagen (formato no soportado o datos corruptos).")
    return frame


def calcular_ear(ojo):
    """Eye Aspect Ratio a partir de los 6 landmarks del ojo (ver README)."""
    def dist(a, b):
        return float(np.linalg.norm(np.array(a) - np.array(b)))

    a = dist(ojo[1], ojo[5])
    b = dist(ojo[2], ojo[4])
    c = dist(ojo[0], ojo[3])
    return (a + b) / (2.0 * c)


@app.route("/")
def index():
    return render_template(
        "index.html",
        parpadeos_requeridos=PARPADEOS_REQUERIDOS,
        ear_umbral=EAR_UMBRAL,
        umbral_distancia=UMBRAL_DISTANCIA,
    )


@app.route("/health")
def health():
    """Endpoint ligero para el HEALTHCHECK de Docker."""
    return jsonify({"status": "ok"})


@app.route("/api/usuarios", methods=["GET"])
def usuarios():
    return jsonify({"usuarios": listar_usuarios()})


@app.route("/api/usuarios/<nombre>", methods=["DELETE"])
def borrar_usuario(nombre):
    ruta = ruta_usuario(nombre)
    if ruta is None or not ruta.exists():
        return jsonify({"status": "error", "message": "Ese usuario no está registrado."}), 404
    ruta.unlink()
    logger.info("Usuario eliminado: %s", nombre)
    return jsonify({"status": "ok", "message": f'Usuario "{nombre}" eliminado.', "usuarios": listar_usuarios()})


@app.route("/api/registrar", methods=["POST"])
def registrar():
    data = request.get_json(silent=True) or {}

    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"status": "error", "message": "Indica un nombre de usuario antes de registrar."}), 400

    ruta = ruta_usuario(nombre)
    if ruta is None:
        return jsonify({"status": "error", "message": "Nombre de usuario no válido (usa letras, números, - o _)."}), 400

    if "image" not in data:
        return jsonify({"status": "error", "message": "No se ha recibido ninguna imagen."}), 400

    try:
        frame = base64_to_cv2(data["image"])
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    if len(boxes) != 1:
        return jsonify({"status": "error", "message": f"Se detectaron {len(boxes)} rostros. Debe haber exactamente 1."})

    encoding = face_recognition.face_encodings(rgb, boxes)[0]
    np.save(ruta, encoding)
    logger.info("Usuario registrado: %s", nombre)
    return jsonify(
        {
            "status": "ok",
            "message": f'Rostro de "{nombre}" registrado con éxito.',
            "usuarios": listar_usuarios(),
        }
    )


@app.route("/api/verificar", methods=["POST"])
def verificar():
    usuarios_registrados = listar_usuarios()
    if not usuarios_registrados:
        return jsonify({"status": "error", "message": "No hay ningún usuario registrado aún."})

    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()

    if "image" not in data:
        return jsonify({"status": "error", "message": "No se ha recibido ninguna imagen."}), 400
    try:
        frame = base64_to_cv2(data["image"])
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)
    landmarks_list = face_recognition.face_landmarks(rgb, boxes)

    if not encodings:
        return jsonify({"status": "no_face", "message": "Buscando rostro..."})

    encoding_actual = encodings[0]

    # Modo 1:1 (verificación): el cliente indica contra quién comparar.
    # Modo 1:N (identificación): sin nombre, se compara contra toda la base.
    if nombre:
        ruta = ruta_usuario(nombre)
        if ruta is None or not ruta.exists():
            return jsonify({"status": "error", "message": f'El usuario "{nombre}" no está registrado.'}), 404
        candidatos = {nombre: ruta}
    else:
        candidatos = {u: ruta_usuario(u) for u in usuarios_registrados}

    mejor_usuario = None
    mejor_distancia = None
    for usuario, ruta_candidato in candidatos.items():
        encoding_guardado = np.load(ruta_candidato)
        distancia = float(face_recognition.face_distance([encoding_guardado], encoding_actual)[0])
        if mejor_distancia is None or distancia < mejor_distancia:
            mejor_distancia = distancia
            mejor_usuario = usuario

    reconocido = bool(mejor_distancia is not None and mejor_distancia <= UMBRAL_DISTANCIA)

    # Evaluación EAR para Liveness
    ear = 0.0
    if reconocido and landmarks_list:
        lm = landmarks_list[0]
        ear_izq = calcular_ear(lm["left_eye"])
        ear_der = calcular_ear(lm["right_eye"])
        ear = (ear_izq + ear_der) / 2.0

    return jsonify(
        {
            "status": "ok",
            "reconocido": reconocido,
            "usuario": mejor_usuario if reconocido else None,
            "distancia": round(mejor_distancia, 2) if mejor_distancia is not None else None,
            "ear": round(float(ear), 2),
            "ojo_cerrado": bool(ear < EAR_UMBRAL),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
