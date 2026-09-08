import pyotp
import qrcode
import time

def ejecutar_cli():
    print("=" * 60)
    print("  LABORATORIO TOTP (RFC 6238) - MODO CONSOLA")
    print("=" * 60)

    # 1. Generar semilla secreta en Base32
    secret = pyotp.random_base32()
    print(f"\\n[1] Clave Secreta en Base32 generada: {secret}")

    # 2. Crear URI estándar de OTP
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name="usuario@ejemplo.com", 
        issuer_name="CursoCiberseguridad"
    )

    # 3. Mostrar código QR en consola ASCII
    print("\\n[2] Escanea este código QR con tu app MFA (Aegis, Google Auth, FreeOTP):\\n")
    qr = qrcode.QRCode()
    qr.add_data(uri)
    qr.print_ascii(invert=True)

    print(f"\\nURI de Aprovisionamiento: {uri}\\n")
    print("-" * 60)

    totp = pyotp.TOTP(secret)

    # 4. Bucle de verificación de Tokens
    while True:
        tiempo_restante = 30 - (int(time.time()) % 30)
        print(f"\\n[Tiempo rest. ventana actual: {tiempo_restante}s]")
        token_input = input("Introduce el token de 6 dígitos (o 'q' para salir): ").strip()

        if token_input.lower() == 'q':
            print("Saliendo del laboratorio.")
            break

        # Verificación con tolerancia de ventana de 1 periodo (30s atras/adelante)
        es_valido = totp.verify(token_input, valid_window=1)

        if es_valido:
            print(" [ÉXITO] ¡Token VÁLIDO! Autenticación correcta.")
        else:
            token_esperado = totp.now()
            print(f" [ERROR] Token INVÁLIDO. (El token actual es: {token_esperado})")

if __name__ == "__main__":
    ejecutar_cli()