"""
thumbnail.py — Generación de thumbnails para imágenes, vídeos, HEIC y RAW.
Usa un semáforo para limitar los workers concurrentes y proteger la CPU de la RPi.
Los thumbnails se almacenan en {carpeta}/.thumbnails/{archivo}.jpg de forma
persistente; si ya existen no se regeneran.
"""
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

from config import (
    GALLERY_ROOT,
    THUMB_DIR_NAME,
    THUMB_SIZE,
    THUMB_QUALITY,
    MAX_CONCURRENT_WORKERS,
    THUMB_LOG,
    FORMATOS_VIDEO,
    FORMATOS_RAW,
)

# Configuración del logger para errores de thumbnails
logger = logging.getLogger("thumbnails")
logger.setLevel(logging.ERROR)
_handler = logging.FileHandler(THUMB_LOG)
_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(_handler)

# Semáforo global que limita la concurrencia de generación
_semaforo = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)

TIMEOUT_SEGUNDOS = 30  # Timeout máximo por operación de thumbnail


def ruta_thumbnail(archivo_abs: Path) -> Path:
    """Calcula la ruta esperada del thumbnail para un archivo dado."""
    carpeta_thumb = archivo_abs.parent / THUMB_DIR_NAME
    return carpeta_thumb / (archivo_abs.stem + ".jpg")


def thumbnail_existe(archivo_abs: Path) -> bool:
    """Comprueba si el thumbnail ya existe en disco."""
    return ruta_thumbnail(archivo_abs).exists()


async def generar_thumbnail(archivo_abs: Path) -> Optional[Path]:
    """
    Punto de entrada principal para la generación de thumbnails.
    Detecta el tipo de archivo y delega a la función apropiada.
    Respeta el límite de workers concurrentes mediante el semáforo global.
    Retorna la ruta del thumbnail generado o None si hubo error.
    """
    ext = archivo_abs.suffix.lower()
    thumb_path = ruta_thumbnail(archivo_abs)

    # No regenerar si ya existe
    if thumb_path.exists():
        return thumb_path

    # Crear directorio .thumbnails si no existe
    thumb_path.parent.mkdir(parents=True, exist_ok=True)

    async with _semaforo:
        try:
            if ext in FORMATOS_VIDEO:
                resultado = await asyncio.wait_for(
                    _generar_thumb_video(archivo_abs, thumb_path),
                    timeout=TIMEOUT_SEGUNDOS,
                )
            elif ext in {'.heic', '.heif'}:
                resultado = await asyncio.wait_for(
                    asyncio.to_thread(_generar_thumb_heic, archivo_abs, thumb_path),
                    timeout=TIMEOUT_SEGUNDOS,
                )
            elif ext in FORMATOS_RAW:
                resultado = await asyncio.wait_for(
                    asyncio.to_thread(_generar_thumb_raw, archivo_abs, thumb_path),
                    timeout=TIMEOUT_SEGUNDOS,
                )
            else:
                resultado = await asyncio.wait_for(
                    asyncio.to_thread(_generar_thumb_imagen, archivo_abs, thumb_path),
                    timeout=TIMEOUT_SEGUNDOS,
                )

            return thumb_path if resultado else None

        except asyncio.TimeoutError:
            logger.error("Timeout generando thumbnail: %s", archivo_abs)
            return None
        except Exception as exc:
            logger.error("Error inesperado con '%s': %s", archivo_abs, exc)
            return None


def _generar_thumb_imagen(archivo_abs: Path, dest: Path) -> bool:
    """
    Genera thumbnail para formatos de imagen estándar (JPG, PNG, WEBP, etc.).
    Usa Pillow con conversión a RGB para máxima compatibilidad.
    """
    try:
        from PIL import Image

        with Image.open(archivo_abs) as img:
            # Convertir modos especiales (RGBA, P, etc.) a RGB para guardar como JPEG
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            img.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return True

    except Exception as exc:
        logger.error("Error imagen '%s': %s", archivo_abs, exc)
        return False


def _generar_thumb_heic(archivo_abs: Path, dest: Path) -> bool:
    """
    Genera thumbnail para archivos HEIC/HEIF usando pillow-heif.
    Registra el plugin de HEIF en Pillow para que Image.open() lo soporte.
    """
    try:
        import pillow_heif
        from PIL import Image

        pillow_heif.register_heif_opener()

        with Image.open(archivo_abs) as img:
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            img.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return True

    except ImportError:
        logger.error("pillow-heif no está instalado. HEIC no soportado.")
        return False
    except Exception as exc:
        logger.error("Error HEIC '%s': %s", archivo_abs, exc)
        return False


def _generar_thumb_raw(archivo_abs: Path, dest: Path) -> bool:
    """
    Genera thumbnail para archivos RAW (CR2, NEF, ARW, etc.) usando rawpy + Pillow.
    Si rawpy falla (por ejemplo, formato no reconocido), devuelve False y lo loguea.
    """
    try:
        import rawpy
        from PIL import Image

        with rawpy.imread(str(archivo_abs)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, half_size=True)

        img = Image.fromarray(rgb)
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        img.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return True

    except ImportError:
        logger.error("rawpy/imageio no están instalados. RAW no soportado.")
        return False
    except Exception as exc:
        logger.error("Error RAW '%s': %s", archivo_abs, exc)
        return False


async def _generar_thumb_video(archivo_abs: Path, dest: Path) -> bool:
    """
    Extrae el frame en el segundo 1 de un vídeo usando FFmpeg como subprocess.
    Es async porque usamos asyncio.create_subprocess_exec para no bloquear.
    """
    comando = [
        "ffmpeg",
        "-ss", "00:00:01",
        "-i", str(archivo_abs),
        "-frames:v", "1",
        "-vf", f"scale={THUMB_SIZE[0]}:{THUMB_SIZE[1]}:force_original_aspect_ratio=increase,"
               f"crop={THUMB_SIZE[0]}:{THUMB_SIZE[1]}",
        "-q:v", "5",
        "-y",
        str(dest),
    ]

    try:
        proceso = await asyncio.create_subprocess_exec(
            *comando,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proceso.communicate(), timeout=TIMEOUT_SEGUNDOS)

        if proceso.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore").strip()
            logger.error("FFmpeg falló con '%s': %s", archivo_abs, error_msg)
            return False

        return dest.exists()

    except FileNotFoundError:
        logger.error("FFmpeg no encontrado. Instálalo con: sudo apt install ffmpeg")
        return False
    except asyncio.TimeoutError:
        logger.error("FFmpeg timeout en: %s", archivo_abs)
        return False
    except Exception as exc:
        logger.error("Error vídeo '%s': %s", archivo_abs, exc)
        return False


async def convertir_heic_a_jpeg(archivo_abs: Path) -> Optional[bytes]:
    """
    Convierte un archivo HEIC a JPEG en memoria para servirlo al navegador.
    Los navegadores no renderizan HEIC nativamente, así que lo convertimos on-the-fly.
    Devuelve los bytes del JPEG o None si la conversión falla.
    """
    try:
        import pillow_heif
        from PIL import Image
        import io

        def _convertir() -> bytes:
            pillow_heif.register_heif_opener()
            with Image.open(archivo_abs) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                buffer = io.BytesIO()
                img.save(buffer, "JPEG", quality=90)
                return buffer.getvalue()

        return await asyncio.to_thread(_convertir)

    except Exception as exc:
        logger.error("Error convirtiendo HEIC a JPEG '%s': %s", archivo_abs, exc)
        return None


async def duracion_video(archivo_abs: Path) -> Optional[str]:
    """
    Obtiene la duración de un vídeo usando ffprobe.
    Devuelve string formateado (ej. "1:23") o None si falla.
    """
    comando = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_entries", "format=duration",
        str(archivo_abs),
    ]
    try:
        proceso = await asyncio.create_subprocess_exec(
            *comando,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proceso.communicate(), timeout=10)

        import json
        data = json.loads(stdout.decode())
        segundos = float(data["format"]["duration"])
        minutos = int(segundos // 60)
        secs = int(segundos % 60)
        return f"{minutos}:{secs:02d}"

    except Exception:
        return None
