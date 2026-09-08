import base64
import os
import cv2
import face_recognition
import numpy as np
from flask import Flask, render_template, request, jsonify
from scipy.spatial import distance as dist

app = Flask(__name__)
DATA_PATH = "/app/data/usuario_registrado.npy"
EAR_UMBRAL = 0.21
UMBRAL_DISTANCIA = 0.50

def base64_to_cv2(base64_string):
    encoded_data = base64_string.split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

def calcular_ear(ojo):
    A = dist.euclidean(ojo[1], ojo[5])
    B = dist.euclidean(ojo[2], ojo[4])
    C = dist.euclidean(ojo[0], ojo[3])
    return (A + B) / (2.0 * C)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/registrar', methods=['POST'])
def registrar():
    data = request.json
    frame = base64_to_cv2(data['image'])
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    boxes = face_recognition.face_locations(rgb)
    if len(boxes) != 1:
        return jsonify({'status': 'error', 'message': f'Se detectaron {len(boxes)} rostros. Debe haber exactamente 1.'})
    
    encoding = face_recognition.face_encodings(rgb, boxes)[0]
    np.save(DATA_PATH, encoding)
    return jsonify({'status': 'ok', 'message': 'Rostro registrado con éxito en volumen Docker.'})

@app.route('/api/verificar', methods=['POST'])
def verificar():
    if not os.path.exists(DATA_PATH):
        return jsonify({'status': 'error', 'message': 'No hay ningún usuario registrado aún.'})

    data = request.json
    frame = base64_to_cv2(data['image'])
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    encoding_registrado = np.load(DATA_PATH)

    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)
    landmarks_list = face_recognition.face_landmarks(rgb, boxes)

    if not encodings:
        return jsonify({'status': 'no_face', 'message': 'Buscando rostro...'})

    distancia = face_recognition.face_distance([encoding_registrado], encodings[0])[0]
    reconocido = bool(distancia <= UMBRAL_DISTANCIA)

    # Evaluación EAR para Liveness
    ear = 0.0
    if reconocido and landmarks_list:
        lm = landmarks_list[0]
        ear_izq = calcular_ear(lm['left_eye'])
        ear_der = calcular_ear(lm['right_eye'])
        ear = (ear_izq + ear_der) / 2.0

    return jsonify({
        'status': 'ok',
        'reconocido': reconocido,
        'distancia': round(float(distancia), 2),
        'ear': round(float(ear), 2),
        'ojo_cerrado': bool(ear < EAR_UMBRAL)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)