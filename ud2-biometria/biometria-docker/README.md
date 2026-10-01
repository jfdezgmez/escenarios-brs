# Laboratorio Práctico: Autenticación Biométrica y Detección de Liveness (Docker)

Laboratorio didáctico de **biometría facial** con **detección de vida (liveness)** mediante parpadeo, empaquetado en un único contenedor Docker con interfaz web (Flask + JavaScript). Permite registrar y verificar varios usuarios, y comparar un rostro tanto en modo **verificación 1:1** ("¿eres quien dices ser?") como en modo **identificación 1:N** ("¿quién de los registrados eres?").

---

## 📋 Tabla de Contenidos

- [1. Fundamento Teórico](#1-fundamento-teórico)
  - [1.1. Biometría Facial basada en Embeddings](#11-biometría-facial-basada-en-embeddings)
  - [1.2. Prueba de Vida (Liveness Detection) mediante EAR](#12-prueba-de-vida-liveness-detection-mediante-ear)
  - [1.3. Verificación (1:1) vs. Identificación (1:N)](#13-verificación-11-vs-identificación-1n)
- [2. Arquitectura y Explicación del Código](#2-arquitectura-y-explicación-del-código)
  - [2.1. Infraestructura Docker](#21-infraestructura-docker)
  - [2.2. Backend Flask (`app.py`)](#22-backend-flask-apppy)
  - [2.3. Frontend Web (`templates/index.html`)](#23-frontend-web-templatesindexhtml)
- [3. Instrucciones de Uso](#3-instrucciones-de-uso)
  - [3.1. Prerrequisitos](#31-prerrequisitos)
  - [3.2. Estructura de Archivos](#32-estructura-de-archivos)
  - [3.3. Variables de Entorno](#33-variables-de-entorno)
  - [3.4. Despliegue](#34-despliegue)
- [4. Casos de Prueba](#4-casos-de-prueba)
- [5. Limitaciones conocidas y posibles ampliaciones](#5-limitaciones-conocidas-y-posibles-ampliaciones)

---

## 1. Fundamento Teórico

### 1.1. Biometría Facial basada en Embeddings
El reconocimiento facial moderno no compara imágenes píxel por píxel. En su lugar, emplea redes neuronales convolucionales para transformar una imagen facial en un vector numérico de 128 dimensiones denominado **Embedding Facial**.

Para determinar si dos rostros pertenecen a la misma persona, se calcula la **Distancia Euclídea** entre sus respectivos vectores ($p$ y $q$):

$$d(p, q) = \sqrt{\sum_{i=1}^{128} (p_i - q_i)^2}$$

* Si $d(p, q) \le 0.50$, el sistema considera que los rostros pertenecen a la misma identidad.
* Si $d(p, q) > 0.50$, se determina que son personas distintas.

### 1.2. Prueba de Vida (Liveness Detection) mediante EAR
Los sistemas biométricos básicos son vulnerables a **Ataques de Presentación (Spoofing)**, como mostrar una fotografía estática frente a la cámara. Para mitigar esta amenaza, se implementa un control de prueba de vida basado en la tasa de aspecto del ojo (**Eye Aspect Ratio - EAR**).

El algoritmo identifica 6 puntos de referencia (*landmarks*) por cada ojo y calcula la relación entre su apertura vertical y horizontal:

$$\text{EAR} = \frac{\Vert{}p_2 - p_6\Vert{} + \Vert{}p_3 - p_5\Vert{}}{2 \cdot \Vert{}p_1 - p_4\Vert{}}$$

* **Ojo abierto:** la distancia vertical es significativamente mayor que cero ($\text{EAR} \approx 0.30$).
* **Ojo cerrado (parpadeo):** la distancia vertical tiende a cero ($\text{EAR} < 0.21$).

Una persona viva muestra una transición de estado (ojo abierto → ojo cerrado → ojo abierto). Una fotografía estática mantiene un valor constante de EAR, impidiendo la autenticación.

> ⚠️ Esta prueba de vida sigue siendo vulnerable a un ataque con un **vídeo** (en lugar de una foto fija) que reproduzca un parpadeo real. Es un liveness básico con fines didácticos, no un sistema anti-spoofing de nivel producción (ver [sección 5](#5-limitaciones-conocidas-y-posibles-ampliaciones)).

### 1.3. Verificación (1:1) vs. Identificación (1:N)
Son los dos modos de uso clásicos de un sistema biométrico, y esta práctica permite experimentar con ambos:

- **Verificación (1:1):** el usuario afirma una identidad ("soy Ana") y el sistema compara su rostro únicamente contra la plantilla guardada de Ana. Es el modo típico de un desbloqueo de móvil o un control de acceso con tarjeta + rostro.
- **Identificación (1:N):** el usuario no indica quién es; el sistema compara su rostro contra **todas** las plantillas registradas y devuelve la más parecida (si supera el umbral). Es el modo típico de un sistema de videovigilancia que busca una cara entre una base de datos.

---

## 2. Arquitectura y Explicación del Código

El proyecto adopta una arquitectura **Cliente-Servidor ligera** empaquetada en Docker:

```text
[ Navegador Web ]  ---(Frames JPEG en Base64 vía HTTP POST)--->  [ Contenedor Docker ]
HTML5 / JS         <---(JSON: Distancia, EAR, Estado)----------  Flask / OpenCV / dlib
```

### 2.1. Infraestructura Docker
- **`Dockerfile`:** usa una compilación **multi-stage**. Una primera etapa compila `dlib` (necesita `cmake`, `g++`, `make`); la imagen final **no incluye esos compiladores**, solo las librerías de sistema necesarias en tiempo de ejecución (`libgl1`, `libglib2.0-0`, `libstdc++6`). Esto reduce notablemente el tamaño de la imagen final. Además, la aplicación se ejecuta con un usuario sin privilegios (`appuser`) y se expone un `HEALTHCHECK` contra `/health`.
- **`docker-compose.yml`:** mapea un volumen local (`./data`) hacia el contenedor (`/app/data`) para guardar las plantillas biométricas de forma persistente, y define los umbrales del laboratorio como variables de entorno.

### 2.2. Backend Flask (`app.py`)
- **`base64_to_cv2()`**: convierte las imágenes capturadas por el navegador en matrices de OpenCV, con manejo de errores explícito (una imagen corrupta o un base64 inválido devuelven un `400` claro en lugar de tumbar la petición con un error 500).
- **Gestión multiusuario**: cada usuario registrado se guarda como `data/usuarios/<nombre>.npy`. El nombre se sanea (solo ASCII alfanumérico, `-` y `_`) antes de tocar el sistema de archivos, para evitar cualquier intento de *path traversal*.
- **Endpoint `POST /api/registrar`**: recibe una foto y un `nombre`, valida que exista únicamente un rostro, genera su embedding de 128 dimensiones con `face_recognition` y lo guarda.
- **Endpoint `POST /api/verificar`**: si se indica un `nombre`, compara en modo 1:1 contra ese usuario; si no, compara en modo 1:N contra todos los usuarios registrados y devuelve el más parecido. Calcula también el EAR medio de ambos ojos para la prueba de vida.
- **Endpoint `GET /api/usuarios`** y **`DELETE /api/usuarios/<nombre>`**: listar y eliminar usuarios registrados, útil para reiniciar la práctica cuando haga falta.
- **Endpoint `GET /health`**: usado por el `HEALTHCHECK` de Docker.
- **Umbrales configurables**: `EAR_UMBRAL`, `UMBRAL_DISTANCIA` y `PARPADEOS_REQUERIDOS` se leen de variables de entorno (ver [3.3](#33-variables-de-entorno)) en vez de estar fijos en el código, y se muestran también en la propia interfaz web para que sepas en todo momento contra qué valores se está comparando.

### 2.3. Frontend Web (`templates/index.html`)
- **Captura de cámara:** usa `navigator.mediaDevices.getUserMedia` para acceder a la cámara del host sin requerir GUI dentro del contenedor.
- **Registro multiusuario:** un campo de texto para el nombre antes de registrar, y un desplegable que lista los usuarios ya registrados (con opción de actualizarlo o eliminar el seleccionado).
- **Modo de verificación:** el mismo desplegable permite elegir "Identificación 1:N (comparar con todos)" o un usuario concreto para verificación 1:1.
- **Bucle de polling:** ejecuta peticiones periódicas a 5 FPS (cada 200 ms) hacia el servidor, procesando la respuesta en tiempo real para verificar el cumplimiento secuencial de parpadeos requeridos.

---

## 3. Instrucciones de Uso

### 3.1. Prerrequisitos
* Tener instalado **Docker** y **Docker Compose** en la máquina anfitriona (Windows, macOS o Linux).

### 3.2. Estructura de Archivos

```text
biometria-docker/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app.py
├── .gitignore / .dockerignore
├── data/
│   └── usuarios/        --> plantillas .npy por usuario (se crean en tiempo de ejecución)
└── templates/
    └── index.html
```

> **Importante:** este repositorio **no** incluye ninguna plantilla biométrica de ejemplo. Cada despliegue empieza sin usuarios registrados; cada usuario registra su propio rostro al hacer la práctica. Las plantillas que se generen se guardan solo en tu `./data/usuarios` local (excluido de git) y nunca deben compartirse ni subirse a un repositorio público.

### 3.3. Variables de Entorno

Todas son opcionales; `docker-compose.yml` ya trae valores por defecto razonables para empezar:

| Variable | Por defecto | Descripción |
|---|---|---|
| `EAR_UMBRAL` | `0.21` | Por debajo de este valor de EAR se considera que el ojo está cerrado. |
| `UMBRAL_DISTANCIA` | `0.50` | Distancia euclídea máxima entre embeddings para considerar que es la misma persona. |
| `PARPADEOS_REQUERIDOS` | `2` | Número de parpadeos completos necesarios para conceder el acceso. |

### 3.4. Despliegue

Clona/descarga el proyecto y sitúate en la terminal dentro de la carpeta `biometria-docker`, después:

```bash
docker compose up --build
```

Abre el navegador en [http://localhost:5000](http://localhost:5000) y concede permisos de acceso a la webcam cuando se soliciten.

---

## 4. Casos de Prueba

**Prueba 1: Registro e Identificación Legítima**
1. Escribe un nombre de usuario y haz clic en **"1. Registrar Rostro"** enfocado hacia la cámara.
2. Deja el desplegable en "Identificación 1:N" (o selecciona tu usuario para 1:1) y haz clic en **"2. Iniciar / Detener Verificación"**.
3. Mira a la cámara y parpadea voluntariamente el número de veces configurado (2 por defecto).
4. **Resultado esperado:** el sistema valida la firma biométrica y los parpadeos, mostrando `¡ACCESO CONCEDIDO!` junto con el nombre de usuario identificado.

**Prueba 2: Simulación de Ataque de Presentación (Spoofing)**
1. Con un usuario ya registrado, toma una foto de tu rostro con un smartphone.
2. Haz clic en **"2. Iniciar / Detener Verificación"**.
3. Muestra la pantalla del móvil con la fotografía frente a la webcam.
4. **Resultado esperado:** el sistema identifica la similitud del rostro, pero el contador de parpadeos permanece congelado en `0/2`, bloqueando el acceso.

**Prueba 3: Identificación entre varios usuarios (1:N)**
1. Registra a dos o más usuarios distintos.
2. Deja el desplegable en "Identificación 1:N" e inicia la verificación con cualquiera de ellos delante de la cámara.
3. **Resultado esperado:** el sistema indica automáticamente **cuál** de los usuarios registrados eres, sin que lo hayas especificado tú.

**Prueba 4: Verificación 1:1 contra la persona equivocada**
1. Con dos usuarios registrados (p. ej. `ana` y `luis`), selecciona `ana` en el desplegable mientras `luis` está delante de la cámara.
2. **Resultado esperado:** `Rostro no reconocido`, aunque `luis` sí esté registrado en el sistema con otro nombre.

---

## 5. Limitaciones conocidas y posibles ampliaciones

- El liveness por parpadeo es básico: no resiste un ataque con **vídeo** (en lugar de foto fija) de la persona parpadeando. Una ampliación natural sería añadir un reto aleatorio (p. ej. "gira la cabeza a la izquierda") para dificultar la reproducción de un vídeo pregrabado.
- No hay autenticación de quién puede registrar o borrar usuarios: en un despliegue donde varias personas comparten el mismo contenedor bajo supervisión esto puede ser aceptable, pero no sería válido en producción sin control de acceso administrativo.
- El almacenamiento es un fichero `.npy` por usuario en disco; para una base de usuarios grande convendría una base de datos vectorial, pero para un laboratorio con un número reducido de usuarios es más que suficiente y mucho más fácil de inspeccionar.
