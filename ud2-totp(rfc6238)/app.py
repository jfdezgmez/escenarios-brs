import base64
import hashlib
import hmac
import io
import os
import secrets
import struct
import time

import pyotp
import qrcode
from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)

# Clave usada para firmar la cookie de sesión. Si no se define por entorno,
# se genera una al arrancar (válida mientras viva el contenedor).
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

# --- Parámetros del laboratorio, configurables por variable de entorno ---
# Ventana máxima de tolerancia que el servidor acepta, pase lo que pase el cliente.
MAX_VENTANA = int(os.environ.get("TOTP_MAX_VENTANA", 2))
# Intentos fallidos consecutivos antes de bloquear temporalmente la verificación.
MAX_INTENTOS = int(os.environ.get("TOTP_MAX_INTENTOS", 5))
# Duración del bloqueo, en segundos.
BLOQUEO_SEGUNDOS = int(os.environ.get("TOTP_BLOQUEO_SEGUNDOS", 30))


def obtener_secreto():
    """Devuelve la semilla TOTP de la sesión actual, generándola si es la primera visita.

    Cada pestaña/navegador recibe su propia semilla en una cookie de sesión firmada
    (no hay almacenamiento en el servidor). Esto evita que dos personas que acceden
    al mismo servidor compartan, sin saberlo, una única identidad MFA global.
    """
    if "totp_secret" not in session:
        session["totp_secret"] = pyotp.random_base32()
    return session["totp_secret"]


def desglosar_rfc6238(secret_b32, time_step=30, digits=6):
    """Calcula el TOTP de forma artesanal según el RFC 6238 mostrando pasos matemáticos."""
    t_time = int(time.time())

    # Decodificar Base32
    padding = len(secret_b32) % 8
    padded_secret = secret_b32 + ("=" * (8 - padding) if padding else "")
    key_bytes = base64.b32decode(padded_secret, casefold=True)

    counter = t_time // time_step
    time_remaining = time_step - (t_time % time_step)

    # Pack counter a 8 bytes big-endian
    msg = struct.pack(">Q", counter)

    # HMAC-SHA1
    hmac_digest = hmac.new(key_bytes, msg, hashlib.sha1).digest()

    # Dynamic Truncation
    offset = hmac_digest[-1] & 0x0F
    binary_code = struct.unpack(">I", hmac_digest[offset : offset + 4])[0] & 0x7FFFFFFF

    otp = binary_code % (10**digits)
    otp_str = f"{otp:0{digits}d}"

    return {
        "unix_time": t_time,
        "counter": counter,
        "time_remaining": time_remaining,
        "hmac_hex": hmac_digest.hex(),
        "offset": offset,
        "binary_code": binary_code,
        "otp": otp_str,
    }


def generar_qr_base64(uri):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


@app.route("/")
def index():
    secret = obtener_secreto()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="usuario@laboratorio.local", issuer_name="Ciberseguridad-TOTP")
    qr_b64 = generar_qr_base64(uri)
    return render_template(
        "index.html",
        secret=secret,
        qr_b64=qr_b64,
        uri=uri,
        max_ventana=MAX_VENTANA,
        max_intentos=MAX_INTENTOS,
        bloqueo_segundos=BLOQUEO_SEGUNDOS,
    )


@app.route("/health")
def health():
    """Endpoint ligero para el HEALTHCHECK de Docker."""
    return jsonify({"status": "ok"})


@app.route("/api/reiniciar", methods=["POST"])
def reiniciar():
    """Genera una nueva semilla para la sesión actual.

    Permite reiniciar la práctica (nuevo secreto, nuevo QR) sin tener que
    reiniciar el contenedor ni afectar a las sesiones de otros usuarios.
    """
    session["totp_secret"] = pyotp.random_base32()
    session.pop("intentos_fallidos", None)
    session.pop("bloqueado_hasta", None)

    secret = session["totp_secret"]
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="usuario@laboratorio.local", issuer_name="Ciberseguridad-TOTP")
    return jsonify({"secret": secret, "uri": uri, "qr_b64": generar_qr_base64(uri)})


@app.route("/api/estado", methods=["GET"])
def estado():
    secret = obtener_secreto()
    desglose = desglosar_rfc6238(secret)
    desglose["pyotp_check"] = pyotp.TOTP(secret).now()
    return jsonify(desglose)


@app.route("/api/verificar", methods=["POST"])
def verificar():
    secret = obtener_secreto()

    # --- Bloqueo anti-fuerza-bruta ---
    ahora = time.time()
    bloqueado_hasta = session.get("bloqueado_hasta", 0)
    if ahora < bloqueado_hasta:
        return (
            jsonify(
                {
                    "valido": False,
                    "bloqueado": True,
                    "segundos_restantes": int(bloqueado_hasta - ahora),
                    "message": "Demasiados intentos fallidos. Espera antes de volver a intentarlo.",
                }
            ),
            429,
        )

    data = request.get_json(silent=True) or {}
    # str() defensivo: si llega un valor no-string (p. ej. un número JSON),
    # el .strip() de la versión original lanzaría un error 500.
    token = str(data.get("token", "")).strip()

    try:
        ventana = int(data.get("window", 0))
    except (TypeError, ValueError):
        ventana = 0
    # Nunca confiamos en una ventana de tolerancia ilimitada procedente del
    # cliente: una ventana enorme ampliaría artificialmente el rango de
    # códigos válidos (más fácil de acertar) y forzaría un cálculo costoso
    # en el servidor (cada unidad de ventana son 2 HMAC-SHA1 adicionales).
    ventana = max(0, min(ventana, MAX_VENTANA))

    totp = pyotp.TOTP(secret)
    es_valido = bool(token) and totp.verify(token, valid_window=ventana)

    if es_valido:
        session["intentos_fallidos"] = 0
        session.pop("bloqueado_hasta", None)
    else:
        intentos = session.get("intentos_fallidos", 0) + 1
        session["intentos_fallidos"] = intentos
        if intentos >= MAX_INTENTOS:
            session["bloqueado_hasta"] = ahora + BLOQUEO_SEGUNDOS
            session["intentos_fallidos"] = 0

    return jsonify(
        {
            "valido": es_valido,
            "token_ingresado": token,
            "token_actual": totp.now(),
            "window_usada": ventana,
            "intentos_restantes": max(0, MAX_INTENTOS - session.get("intentos_fallidos", 0)),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
