#!/bin/sh
# El contenedor arranca como root únicamente para poder corregir los permisos
# del volumen ./data montado desde el host (docker-compose.yml). Ese volumen
# puede pertenecer a otro usuario del host (o no existir todavía la primera
# vez), así que nos aseguramos de que "appuser" pueda escribir en él antes
# de arrancar la aplicación.
set -e

mkdir -p /app/data/usuarios
chown -R appuser:appuser /app/data

# A partir de aquí la aplicación ya se ejecuta sin privilegios de root.
exec setpriv --reuid=appuser --regid=appuser --init-groups "$@"
