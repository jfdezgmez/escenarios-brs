import base64
import time
import hmac
import hashlib
import struct
import io
import pyotp
import qrcode
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Generar una semilla secreta persistente durante la ejecución
SECRET_KEY = pyotp.random_base32()

def desglosar_rfc6238(secret_b32, time_step=30, digits=6):
    """Calcula el TOTP de forma artesanal según el RFC 6238 mostrando pasos matemáticos."""
    t_time = int(time.time())
    
    # Decodificar Base32
    padding = len(secret_b32) % 8
    padded_secret = secret_b32 + ('=' * (8 - padding) if padding else '')
    key_bytes = base64.b32decode(padded_secret, casefold=True)
    
    counter = t_time // time_step
    time_remaining = time_step - (t_time % time_step)
    
    # Pack counter a 8 bytes big-endian
    msg = struct.pack(">Q", counter)
    
    # HMAC-SHA1
    hmac_digest = hmac.new(key_bytes, msg, hashlib.sha1).digest()
    
    # Dynamic Truncation
    offset = hmac_digest[-1] & 0x0F
    binary_code = struct.unpack(">I", hmac_digest[offset:offset+4])[0] & 0x7FFFFFFF
    
    otp = binary_code % (10 ** digits)
    otp_str = f"{otp:0{digits}d}"
    
    return {
        "unix_time": t_time,
        "counter": counter,
        "time_remaining": time_remaining,
        "hmac_hex": hmac_digest.hex(),
        "offset": offset,
        "binary_code": binary_code,
        "otp": otp_str
    }

def generar_qr_base64(uri):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.route('/')
def index():
    totp = pyotp.TOTP(SECRET_KEY)
    uri = totp.provisioning_uri(name="alumno@laboratorio.local", issuer_name="Ciberseguridad-TOTP")
    qr_b64 = generar_qr_base64(uri)
    return render_template('index.html', secret=SECRET_KEY, qr_b64=qr_b64, uri=uri)

@app.route('/api/estado', methods=['GET'])
def estado():
    desglose = desglosar_rfc6238(SECRET_KEY)
    totp_pyotp = pyotp.TOTP(SECRET_KEY).now()
    desglose['pyotp_check'] = totp_pyotp
    return jsonify(desglose)

@app.route('/api/verificar', methods=['POST'])
def verificar():
    data = request.json or {}
    token = data.get('token', '').strip()
    window = int(data.get('window', 0))
    
    totp = pyotp.TOTP(SECRET_KEY)
    es_valido = totp.verify(token, valid_window=window)
    
    return jsonify({
        'valido': es_valido,
        'token_ingresado': token,
        'token_actual': totp.now(),
        'window_usada': window
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)