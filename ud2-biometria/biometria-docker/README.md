# Laboratorio Práctico: Autenticación Biométrica y Detección de Liveness (Docker)

## 1. Fundamento Teórico

### Biometría Facial basada en Embeddings
El reconocimiento facial moderno no compara imágenes píxel por píxel. En su lugar, emplea redes neuronales convolucionales para transformar una imagen facial en un vector numérico de 128 dimensiones denominado **Embedding Facial**. 

Para determinar si dos rostros pertenecen a la misma persona, se calcula la **Distancia Euclídea** entre sus respectivos vectores ($p$ y $q$):

$$d(p, q) = \sqrt{\sum_{i=1}^{128} (p_i - q_i)^2}$$

* Si $d(p, q) \le 0.50$, el sistema considera que los rostros pertenecen a la misma identidad.
* Si $d(p, q) > 0.50$, se determina que son personas distintas.

### Prueba de Vida (Liveness Detection) mediante EAR
Los sistemas biométricos básicos son vulnerables a **Ataques de Presentación (Spoofing)**, como mostrar una fotografía estática frente a la cámara. Para mitigar esta amenaza, se implementa un control de prueba de vida basado en la tasa de aspecto del ojo (**Eye Aspect Ratio - EAR**).

El algoritmo identifica 6 puntos de referencia (*landmarks*) por cada ojo y calcula la relación entre su apertura vertical y horizontal:

$$\text{EAR} = \frac{\Vert{}p_2 - p_6\Vert{} + \Vert{}p_3 - p_5\Vert{}}{2 \cdot \Vert{}p_1 - p_4\Vert{}}$$

* **Ojo abierto:** La distancia vertical es significativamente mayor que cero ($\text{EAR} \approx 0.30$).
* **Ojo cerrado (Parpadeo):** La distancia vertical tiende a cero ($\text{EAR} < 0.21$).

Una persona viva muestra una transición de estado $(\text{Ojo Abierto} \to \text{Ojo Cerrado} \to \text{Ojo Abierto})$. Una fotografía estática mantiene un valor constante de EAR, impidiendo la autenticación.

---

## 2. Explicación del Código y Funcionamiento

El proyecto adopta una arquitectura **Cliente-Servidor ligera** empaquetada en Docker:

[ Navegador Web ]  ---(Frames JPEG en Base64 via HTTP POST)--->  [ Contenedor Docker ]
HTML5 / JS       <---(JSON: Distancia, EAR, Estado)-----------   Flask / OpenCV / Dlib

### Componentes Principales

1. **Infraestructura (`Dockerfile` y `docker-compose.yml`)**
   * Utiliza una imagen base ligera de Python (`python:3.10-slim`).
   * Instala los paquetes de compilación del sistema (`cmake`, `g++`, `make`) necesarios para compilar la librería de visión artificial `dlib`.
   * Mapea un volumen local (`./data`) hacia el contenedor (`/app/data`) para guardar la plantilla biométrica de forma persistente.

2. **Backend Flask (`app.py`)**
   * **`base64_to_cv2()`**: Convierte las imágenes capturadas por el navegador web en matrices decodificables por OpenCV.
   * **Endpoint `/api/registrar`**: Recibe una foto inicial, valida que exista únicamente un rostro, genera su embedding de 128 dimensiones con `face_recognition` y lo almacena en el archivo `usuario_registrado.npy`.
   * **Endpoint `/api/verificar`**: Analiza el frame enviado por el navegador. Extrae la distancia euclídea respecto al registro guardado y calcula el promedio del indicador EAR entre ambos ojos.

3. **Frontend Web (`templates/index.html`)**
   * **Captura de Cámara:** Emplea la API nativa de JavaScript `navigator.mediaDevices.getUserMedia` para acceder a la cámara nativa del sistema host sin requerir configuraciones de GUI dentro del contenedor.
   * **Bucle de Polling:** Ejecuta peticiones periódicas a 5 FPS hacia el servidor, procesando la respuesta en tiempo real para verificar el cumplimiento secuencial de parpadeos requeridos ($2/2$).

---

## 3. Instrucciones de Uso

### Prerrequisitos
* Tener instalado **Docker** y **Docker Compose** en la máquina anfitriona (Windows, macOS o Linux).

### Estructura de Archivos
Asegúrate de organizar los archivos del proyecto en la siguiente estructura antes de iniciar:

```text
biometria-docker/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app.py
└── templates/
    └── index.html
```

Pasos para el Despliegue
Clonar/Descargar el proyecto y situarse en la terminal dentro de la carpeta biometria-docker.

Iniciar la aplicación:

```bash
docker compose up --build
```

Acceder a la aplicación:
Abre el navegador e ingresa a http://localhost:5000. Concede permisos de acceso a la webcam cuando el navegador lo solicite.

### Casos de Prueba
Prueba 1: Registro e Identificación Legítima

Haz clic en el botón "1. Registrar Rostro" enfocado hacia la cámara.

Haz clic en "2. Iniciar / Detener Verificación".

Mira a la cámara y parpadea voluntariamente 2 veces.

Resultado esperado: El sistema validará la firma biométrica y los parpadeos, mostrando el mensaje ¡ACCESO CONCEDIDO!.

Prueba 2: Simulación de Ataque de Presentación (Spoofing)

Con el usuario ya registrado, toma una foto de tu rostro usando un smartphone.

Haz clic en "2. Iniciar / Detener Verificación".

Muestra la pantalla del móvil con tu fotografía frente a la webcam.

Resultado esperado: El sistema identificará la similitud del rostro, pero el contador de parpadeos permanecerá congelado en 0/2, bloqueando el acceso.