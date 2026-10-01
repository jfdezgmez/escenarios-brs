# Escenarios de Prácticas — Bastionado de Redes y Sistemas (BRS)

Repositorio con **escenarios de laboratorio dockerizados** sobre autenticación y control de acceso, pensados para practicarse de forma autocontenida: cada escenario es un contenedor independiente con interfaz web, sin más dependencia que Docker.

Incluye dos escenarios:

| Escenario | Qué practica | Carpeta |
|---|---|---|
| 🧑‍💻 **Biometría + Liveness** | Reconocimiento facial por embeddings, prueba de vida (parpadeo), verificación 1:1 e identificación 1:N | [`ud2-biometria/biometria-docker`](ud2-biometria/biometria-docker) |
| 🔐 **TOTP (RFC 6238)** | Algoritmo de doble factor basado en tiempo (HOTP → TOTP), enrolamiento con QR, tolerancia de ventana, bloqueo anti-fuerza-bruta | [`ud2-totp(rfc6238)`](<ud2-totp(rfc6238)>) |

---

## 📋 Tabla de Contenidos

- [1. Requisitos Generales](#1-requisitos-generales)
- [2. Arranque Rápido](#2-arranque-rápido)
- [3. Estructura del Repositorio](#3-estructura-del-repositorio)
- [4. Qué tiene cada escenario](#4-qué-tiene-cada-escenario)
- [5. Buenas prácticas aplicadas en ambos escenarios](#5-buenas-prácticas-aplicadas-en-ambos-escenarios)
- [6. Limitaciones y alcance](#6-limitaciones-y-alcance)

---

## 1. Requisitos Generales

- **Docker** y **Docker Compose** (todo lo demás —Python, Flask, OpenCV, etc.— vive dentro del contenedor).
- Un navegador con acceso a cámara web (solo para el escenario de biometría) y/o una app de autenticación MFA como Aegis, Google Authenticator o FreeOTP (solo para el escenario TOTP).

No hace falta instalar nada más en el host: no se necesita Python, pip ni ninguna librería del sistema fuera del contenedor.

## 2. Arranque Rápido

Cada escenario se levanta de forma independiente desde su propia carpeta:

```bash
# Biometría + Liveness
cd ud2-biometria/biometria-docker
docker compose up --build
# -> http://localhost:5000

# TOTP (RFC 6238)
cd "ud2-totp(rfc6238)"
docker compose up --build
# -> http://localhost:5000
```

> ⚠️ **Los dos escenarios usan el puerto 5000 por defecto.** Si quieres tenerlos arrancados a la vez, cambia el mapeo de puertos de uno de los dos en su `docker-compose.yml` (por ejemplo, `"5001:5000"`) antes de levantarlo.

Cada carpeta tiene su propio README con el fundamento teórico, la explicación fichero por fichero, las variables de entorno disponibles y los casos de prueba sugeridos — consúltalo antes de empezar la práctica correspondiente.

## 3. Estructura del Repositorio

```text
.
├── README.md                      --> este fichero
├── ud2-biometria/
│   └── biometria-docker/          --> escenario de biometría facial + liveness
│       ├── README.md
│       ├── Dockerfile
│       ├── docker-compose.yml
│       ├── app.py
│       └── templates/
└── ud2-totp(rfc6238)/              --> escenario de TOTP (RFC 6238)
    ├── README.md
    ├── Dockerfile
    ├── docker-compose.yml
    ├── app.py
    ├── cli.py
    └── templates/
```

## 4. Qué tiene cada escenario

### [Biometría + Liveness](ud2-biometria/biometria-docker)
- Registro e identificación facial mediante embeddings de 128 dimensiones (`face_recognition`/dlib).
- Prueba de vida por parpadeo (Eye Aspect Ratio, EAR), para detectar un ataque con foto estática.
- Soporta **varios usuarios registrados** a la vez: verificación 1:1 contra un usuario concreto, o identificación 1:N contra toda la base.
- Imagen Docker **multi-stage**: la imagen final no incluye los compiladores necesarios para construir `dlib`, solo las librerías de ejecución.

### [TOTP (RFC 6238)](<ud2-totp(rfc6238)>)
- Desglose matemático en tiempo real del algoritmo (HMAC-SHA1, truncado dinámico, contador temporal), verificado contra los vectores de prueba oficiales del RFC 4226.
- Enrolamiento con código QR (`otpauth://`) compatible con cualquier app TOTP estándar.
- Cada sesión de navegador recibe su **propia semilla independiente** (no se comparte entre quienes usan el mismo servidor).
- Bloqueo temporal tras varios intentos fallidos, y botón para reiniciar la práctica sin reiniciar el contenedor.
- Incluye también una versión de consola (`cli.py`) con QR en ASCII.

## 5. Buenas prácticas aplicadas en ambos escenarios

- Contenedores ejecutados con un **usuario sin privilegios** (no root).
- `HEALTHCHECK` en el `Dockerfile` para que Docker pueda detectar si el servicio deja de responder.
- Umbrales y parámetros configurables por **variable de entorno** en lugar de estar fijos en el código.
- `.gitignore` / `.dockerignore` para que ningún dato generado en tiempo de ejecución (plantillas biométricas, cookies de sesión, cachés) acabe en el control de versiones ni en la imagen.
- Validación de errores explícita en las APIs (una entrada mal formada devuelve un error controlado, no un fallo del servidor).

## 6. Limitaciones y alcance

Son laboratorios didácticos: priorizan que el funcionamiento interno del algoritmo se pueda **ver y seguir paso a paso**, no un hardening de nivel producción. Cada README de escenario detalla sus propias limitaciones conocidas y posibles ampliaciones.
