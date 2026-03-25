import os

# CONFIGURACIÓN GENERAL DEL SERVIDOR
# -----------------------------------------------------------------------------
# Ruta raíz donde se encuentran las fotos y vídeos
# Prevenir navegación por encima de esta ruta por seguridad
GALLERY_ROOT = "/opt/atelier/files/photos"

# Directorio de caché para thumbnails (dentro de cada carpeta)
THUMB_DIR_NAME = ".thumbnails"

# PUERTO Y HOST
HOST = "0.0.0.0"
PORT = 8080

# CONFIGURACIÓN DE THUMBNAILS
# -----------------------------------------------------------------------------
THUMB_SIZE = (320, 320)
THUMB_QUALITY = 75  # Balance óptimo de calidad/tamaño para RPi
MAX_CONCURRENT_WORKERS = 2  # Límite para no colapsar la CPU de la RPi

# FORMATOS SOPORTADOS
# -----------------------------------------------------------------------------
FORMATOS_IMAGEN = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.gif', '.bmp', '.tiff', '.tif'}
FORMATOS_VIDEO  = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.wmv'}
FORMATOS_RAW    = {'.raw', '.cr2', '.nef', '.arw'}

# TIEMPOS DE CACHÉ HTTP (Headers para el navegador)
CACHE_MAX_AGE = 86400 * 30  # 30 días para assets estáticos y thumbnails

# LOGS
THUMB_LOG = "thumbnail_errors.log"

# SECURITY NOTE (HTTP Basic Auth)
# Para habilitar seguridad fuera de la LAN local, se recomienda usar un proxy 
# inverso como Nginx con configuración de autenticación básica.
# FastAPI también permite implementar auth middleware si se requiere.
