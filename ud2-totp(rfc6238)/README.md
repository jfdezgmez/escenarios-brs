# Laboratorio Práctico: Implementación del Algoritmo TOTP (RFC 6238)

Este repositorio contiene la implementación práctica y didáctica del algoritmo **TOTP** (*Time-Based One-Time Password*), definido en el **RFC 6238**. El proyecto incluye tanto un backend web interactivo desarrollado en **Flask** con soporte **Docker** como un script ejecutable por consola (**CLI**).

---

## 📋 Tabla de Contenidos

- [1. Fundamento Teórico](#1-fundamento-teórico)
  - [1.1. Introducción a TOTP y MFA](#11-introducción-a-totp-y-múltiple-factor-de-autenticación-mfa)
  - [1.2. Relación entre HOTP y TOTP](#12-relación-entre-hotp-rfc-4226-y-totp-rfc-6238)
  - [1.3. Fases y Matemática del Algoritmo Paso a Paso](#13-fases-y-matemática-del-algoritmo-paso-a-paso)
  - [1.4. Ventana de Tolerancia (Clock Drift / Offset)](#14-ventana-de-tolerancia-clock-drift--offset)
- [2. Estructura y Explicación del Código](#2-estructura-y-explicación-del-código)
  - [2.1. Estructura del Proyecto](#21-estructura-del-proyecto)
  - [2.2. Explicación Fichero por Fichero](#22-explicación-fichero-por-fichero)
- [3. Guía de Uso e Interfaz Web](#3-guía-de-uso-e-interfaz-web)
  - [3.1. Requisitos Previos y Despliegue](#31-requisitos-previos-y-despliegue)
  - [3.2. Uso de la Interfaz Web](#32-uso-de-la-interfaz-web-modo-servidor)
- [4. Ejercicios Prácticos y Experimentos](#4-ejercicios-prácticos-y-experimentos-sugeridos)

---

## 1. Fundamento Teórico

### 1.1. Introducción a TOTP y Múltiple Factor de Autenticación (MFA)
El algoritmo **TOTP** (*Time-Based One-Time Password*), especificado en el **RFC 6238**, es un estándar abierto para la generación de contraseñas de un solo uso basadas en el tiempo. TOTP constituye la base de la mayoría de las aplicaciones de autenticación de segundo factor (2FA/MFA), tales como Google Authenticator, Aegis, Authy, FreeOTP o Microsoft Authenticator.

La principal ventaja del algoritmo TOTP es su capacidad para operar en entornos **completamente fuera de línea (offline)**: ni la aplicación cliente (teléfono móvil) ni el servidor necesitan comunicarse en red durante la generación o verificación del código de 6 dígitos. Ambos extremos solo requieren compartir previamente un secreto (semilla Base32) y disponer de un reloj interno sincronizado mediante tiempo UTC (Unix Epoch).

---

### 1.2. Relación entre HOTP (RFC 4226) y TOTP (RFC 6238)
TOTP es una extensión directa de **HOTP** (*HMAC-Based One-Time Password*, RFC 4226). 

* **HOTP:** Utiliza un contador secuencial $C$ que se incrementa en $+1$ cada vez que se genera o solicita un nuevo token:
  $$\text{HOTP}(K, C) = \text{Truncate}(\text{HMAC-SHA1}(K, C))$$
  *Problema de HOTP:* El servidor y el cliente deben mantener sincronizado el contador implícito. Si el usuario genera varios códigos en la app sin introducirlos en la web, el contador del cliente avanza y se desincroniza con respecto al servidor.

* **TOTP:** Reemplaza el contador arbitrario $C$ por un valor derivado directamente del tiempo del sistema Unix ($T$):
  $$C = \left\lfloor \frac{T - T_0}{X} \right\rfloor$$
  Donde:
  * $T$: Tiempo Unix actual en segundos (*Unix Timestamp*).
  * $T_0$: Marca de tiempo inicial (estándar = $0$).
  * $X$: Duración de la ventana temporal o paso (*Time Step*, por defecto **30 segundos**).

---

### 1.3. Fases y Matemática del Algoritmo Paso a Paso

#### Paso 1: Generación y Enrolamiento de la Semilla Secreta ($K$)
Durante la fase de configuración inicial (enrolamiento):
1. El servidor genera una clave secreta aleatoria $K$ en codificación **Base32** (p. ej. `JBSWY3DPEHPK3PXP`).
2. Se genera un URI normalizado bajo el esquema `otpauth://`:
   ```text
   otpauth://totp/CursoCiberseguridad:alumno@laboratorio.local?secret=JBSWY3DPEHPK3PXP&issuer=CursoCiberseguridad
   ```
3. El URI se codifica en un código QR que el usuario escanea con su aplicación móvil. A partir de este instante, tanto el cliente como el servidor almacenan la misma clave secreta $K$.

#### Paso 2: Cálculo del Contador Temporal ($C$)
El contador de ventana temporal se calcula como:

$$C = \left\lfloor \frac{\text{Unix\_Time}}{30} \right\rfloor$$

Dado que se aplica la función suelo ($\lfloor \rfloor$), el resultado de $C$ se mantiene constante durante intervalos completos de 30 segundos. Por ejemplo, si el tiempo Unix es $1700000012$:

$$C = \lfloor 1700000012 / 30 \rfloor = 56666667$$

#### Paso 3: Generación del Hash HMAC-SHA1
Se calcula la firma digest mediante HMAC utilizando SHA-1 (o SHA-256/SHA-512 según variantes):
1. La clave Base32 $K$ se decodifica a su representación binaria de bytes.
2. El contador $C$ se empaqueta como un entero de 64 bits (8 bytes) en formato **Big-Endian**.
3. Se obtiene el hash digest de 20 bytes (160 bits):

$$\text{HMAC} = \text{HMAC-SHA1}(K_{\text{bytes}}, C_{\text{bytes}})$$

#### Paso 4: Truncado Dinámico (Dynamic Truncation)
Para extraer un número entero representable a partir de los 20 bytes del resultado del hash HMAC:

- **Offset:** Se inspecciona el último nibble (los 4 bits menos significativos) del byte 19 del hash HMAC:
  $$\text{offset} = \text{HMAC}[19] \ \& \ \text{0x0F}$$
- **Extracción de 4 Bytes:** A partir de dicho índice offset, se leen 4 bytes consecutivos del hash HMAC.
- **Máscara de 31 bits:** Se elimina el bit más significativo para evitar ambigüedades con números con signo:
  $$\text{Binary} = ((\text{HMAC}[\text{offset}] \ \& \ \text{0x7F}) \ll 24) \mid ((\text{HMAC}[\text{offset}+1] \ \& \ \text{0xFF}) \ll 16) \mid ((\text{HMAC}[\text{offset}+2] \ \& \ \text{0xFF}) \ll 8) \mid (\text{HMAC}[\text{offset}+3] \ \& \ \text{0xFF})$$

#### Paso 5: Reducción a 6 Dígitos
Se aplica la operación módulo $10^6$ al resultado binario de 31 bits:

$$\text{TOTP} = \text{Binary} \pmod{10^6}$$

Se rellena con ceros a la izquierda si el resultado tiene menos de 6 dígitos.

---

### 1.4. Ventana de Tolerancia (Clock Drift / Offset)

En entornos reales, los relojes de los servidores y de los dispositivos móviles pueden sufrir pequeñas desviaciones (desincronización de segundos). Para mitigar este problema sin comprometer la seguridad, la verificación TOTP evalúa el token en una ventana de tolerancia ($W$):

$$\text{Validar}(T) \iff \text{Token} \in \{ \text{TOTP}(C - W), \dots, \text{TOTP}(C), \dots, \text{TOTP}(C + W) \}$$

Con $W=1$, el servidor acepta el código de la ventana actual (30s), de la ventana inmediatamente anterior (-30s) y de la ventana posterior (+30s).

---

## 2. Estructura y Explicación del Código

### 2.1. Estructura del Proyecto

```text
totp-docker/
├── Dockerfile              --> Imagen base Python 3.10-slim
├── docker-compose.yml      --> Despliegue de servicio en puerto 5000
├── requirements.txt        --> Dependencias del sistema (Flask, pyotp, qrcode, Pillow)
├── cli.py                  --> Script de consola interactiva con QR ASCII
├── app.py                  --> Backend Web Flask y descompositor RFC 6238
└── templates/
    └── index.html          --> Dashboard web interactivo y simulador en tiempo real
```

---

### 2.2. Explicación Fichero por Fichero

#### A. `requirements.txt`
Define las librerías necesarias:
- **`Flask`:** Framework web ligero para servir la API REST y la interfaz gráfica.
- **`pyotp`:** Librería estándar de Python para generación y validación de tokens OTP.
- **`qrcode[pil]` y `Pillow`:** Generación de códigos QR tanto en formato gráfico PNG como en la consola de comandos.

#### B. `Dockerfile` y `docker-compose.yml`
- **`Dockerfile`:** Utiliza la imagen oficial de Python 3.10 en versión reducida (`python:3.10-slim`), instala las dependencias de `requirements.txt` sin guardar caché y expone el puerto 5000.
- **`docker-compose.yml`:** Define el servicio `totp-lab`, asigna el nombre al contenedor `totp_lab_container` y mapea el puerto `5000:5000`.

#### C. Script de Consola (`cli.py`)
Diseñado para la ejecución en línea de comandos según los requisitos de la práctica:
- `pyotp.random_base32()`: Genera la semilla en Base32 aleatoria al arrancar.
- `pyotp.totp.TOTP(secret).provisioning_uri(...)`: Genera la URI bajo la especificación normalizada `otpauth://`.
- `qr.print_ascii(invert=True)`: Renderiza el código QR mediante caracteres unicode/ASCII en la terminal sin necesidad de interfaz gráfica.
- **Bucle de validación:** Lee tokens ingresados por el alumno y ejecuta `totp.verify(token, valid_window=1)`. Si el código es válido, responde con un mensaje de éxito; si no lo es, muestra el token esperado en ese instante para auditoría.

#### D. Backend Servidor Web (`app.py`)
Proporciona endpoints REST y expone la matemática interna del RFC:

- **`desglosar_rfc6238(secret_b32)`:**
  Implementa manualmente la especificación del algoritmo RFC 6238 paso a paso sin depender de abstracciones externas:
  1. Decodifica la clave con `base64.b32decode`.
  2. Empaqueta el contador temporal $C$ mediante `struct.pack(">Q", counter)` (entero de 64 bits Big-Endian).
  3. Calcula el hash HMAC-SHA1 con `hmac.new(key, msg, hashlib.sha1)`.
  4. Realiza el *Dynamic Truncation* extrayendo el nibble del offset y aplicando la máscara de 31 bits con `struct.unpack`.

- **Endpoints:**
  - `GET /`: Renderiza `index.html` pasando la clave secreta y la imagen del código QR codificada en Base64.
  - `GET /api/estado`: Retorna un objeto JSON actualizado con el estado actual del reloj Unix, contador $C$, hash HMAC en hexadecimal, offset, entero truncado binario y el código de 6 dígitos resultante.
  - `POST /api/verificar`: Recibe el token del usuario y la ventana de tolerancia seleccionada, ejecutando la validación.

#### E. Frontend Web (`templates/index.html`)
Ofrece una interfaz visual didáctica con las siguientes secciones:
- **Tarjeta 1 (Enrolamiento):** Muestra el código QR PNG y la semilla de texto en Base32 para permitir enrolamiento manual o mediante cámara.
- **Tarjeta 2 (Validación):** Formulario para ingresar el token de 6 dígitos y seleccionar la tolerancia de ventana ($W = 0, 1, 2$).
- **Tarjeta 3 (Desglose Matemático):** Actualiza cada 1 segundo mediante un intervalo de JavaScript los valores internos del servidor (`unix_time`, `counter`, `hmac_hex`, `offset`, `binary_code`, `otp`), e incluye una barra de progreso visual de 30 a 0 segundos que marca el ciclo de vida de la ventana actual.

---

## 3. Guía de Uso e Interfaz Web

### 3.1. Requisitos Previos y Despliegue

Para desplegar el laboratorio con **Docker Compose**, ejecuta:

```bash
docker-compose up --build
```

### 3.2. Uso de la Interfaz Web (Modo Servidor)

1. **Acceso:** Abre tu navegador e ingresa a [`http://localhost:5000`](http://localhost:5000).
2. **Enrolamiento:**
   - Abre tu aplicación móvil MFA (por ejemplo, **Aegis** o **Google Authenticator**).
   - Pulsa en *Agregar cuenta* y escanea el código QR que aparece en pantalla.
3. **Monitoreo en tiempo real:**
   - Observa la sección **"3. Cálculo Interno del Algoritmo"**.
   - Verás cómo el tiempo Unix avanza segundo a segundo y cómo el contador $C$ permanece constante durante 30 segundos.
   - Compara el código mostrado en la app móvil con el campo **"OTP Calculado"** y con la salida de PyOTP.
4. **Verificación de Token:**
   - Introduce el código de 6 dígitos generado en tu móvil en la tarjeta de validación.
   - Selecciona el grado de tolerancia de ventana ($0$, $1$ o $2$) y haz clic en **"Verificar OTP"**.

---

## 4. Ejercicios Prácticos y Experimentos Sugeridos

- **Prueba de Verificación Off-Line (Modo Avión):**
  - Activa el **Modo Avión** en tu teléfono móvil (desactivando Wi-Fi, Datos y Bluetooth).
  - Genera el token de 6 dígitos en tu app móvil e introdúcelo en la web o consola.
  > **Reflexión:** ¿Por qué la app móvil genera tokens válidos sin tener conexión a Internet?  
  > *(Porque solo requiere la semilla $K$ compartida en el enrolamiento y la hora actual de su reloj interno).*

- **Demostración de Tolerancia de Ventana (Drift):**
  - Espera a que la barra de tiempo esté a punto de finalizar (1 o 2 segundos restantes) e introduce el token justo cuando la barra cambie de ciclo.
  - Cambia la tolerancia en el desplegable de $0$ a $1$ para observar cómo la ventana anterior sigue siendo aceptada por el servidor para evitar falsos negativos por micro-desincronizaciones.