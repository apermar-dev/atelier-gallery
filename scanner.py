"""
scanner.py — Escaneado del sistema de archivos y filtrado por extensión.
Devuelve listas de entradas con metadatos básicos para la vista de galería.
"""
import os
import time
from pathlib import Path
from typing import TypedDict

from config import (
    GALLERY_ROOT,
    FORMATOS_IMAGEN,
    FORMATOS_VIDEO,
    FORMATOS_RAW,
    THUMB_DIR_NAME,
)

# Todos los formatos multimedia reconocidos
TODOS_LOS_FORMATOS = FORMATOS_IMAGEN | FORMATOS_VIDEO | FORMATOS_RAW


class EntradaArchivo(TypedDict):
    nombre: str
    ruta_relativa: str       # Relativa a GALLERY_ROOT, usada en URLs
    tipo: str                # "imagen", "video", "raw", "carpeta"
    extension: str
    tamanio: int             # Bytes (0 para carpetas)
    modificado: float        # Timestamp Unix
    thumb_relativa: str      # Ruta relativa al GALLERY_ROOT para la URL /thumb/


def _resolver_ruta_segura(ruta_relativa: str) -> Path:
    """
    Resuelve una ruta relativa dentro de GALLERY_ROOT de forma segura.
    Lanza ValueError si el path calculado sale de la raíz permitida (path traversal).
    """
    raiz = Path(GALLERY_ROOT).resolve()
    destino = (raiz / ruta_relativa).resolve()

    # Validación crítica: el path resultante debe estar dentro de GALLERY_ROOT
    try:
        destino.relative_to(raiz)
    except ValueError:
        raise ValueError(f"Path traversal detectado: '{ruta_relativa}' sale de la raíz.")

    return destino


def _tipo_de_extension(ext: str) -> str:
    """Clasifica una extensión en 'imagen', 'video', 'raw' o 'desconocido'."""
    ext = ext.lower()
    if ext in FORMATOS_IMAGEN:
        return "imagen"
    if ext in FORMATOS_VIDEO:
        return "video"
    if ext in FORMATOS_RAW:
        return "raw"
    return "desconocido"


def listar_directorio(ruta_relativa: str) -> dict:
    """
    Lista el contenido de un directorio relativo a GALLERY_ROOT.
    Retorna un dict con:
      - 'carpetas': lista de EntradaArchivo de tipo "carpeta"
      - 'archivos': lista de EntradaArchivo de tipos multimedia
      - 'ruta_actual': la ruta relativa normalizada
    """
    ruta_abs = _resolver_ruta_segura(ruta_relativa)

    if not ruta_abs.exists():
        raise FileNotFoundError(f"La ruta no existe: {ruta_abs}")
    if not ruta_abs.is_dir():
        raise NotADirectoryError(f"No es un directorio: {ruta_abs}")

    carpetas: list[EntradaArchivo] = []
    archivos: list[EntradaArchivo] = []

    try:
        entradas = sorted(ruta_abs.iterdir(), key=lambda e: e.name.lower())
    except PermissionError as exc:
        raise PermissionError(f"Sin permiso para leer: {ruta_abs}") from exc

    for entrada in entradas:
        # Ignorar carpetas de thumbnails y archivos ocultos
        if entrada.name.startswith('.'):
            continue

        try:
            stat = entrada.stat()
        except OSError:
            continue  # Ignorar links rotos o inaccesibles

        rel = str(entrada.relative_to(Path(GALLERY_ROOT).resolve()))

        if entrada.is_dir():
            # Buscar el primer archivo de media dentro para usarlo como portada
            primer_thumb = _primer_archivo_en_carpeta(entrada)
            carpetas.append(EntradaArchivo(
                nombre=entrada.name,
                ruta_relativa=rel,
                tipo="carpeta",
                extension="",
                tamanio=0,
                modificado=stat.st_mtime,
                thumb_relativa=primer_thumb,
            ))

        elif entrada.is_file():
            ext = entrada.suffix.lower()
            if ext not in TODOS_LOS_FORMATOS:
                continue

            tipo = _tipo_de_extension(ext)
            # Ruta esperada del thumbnail
            thumb_nombre = entrada.stem + ".jpg"
            thumb_abs = entrada.parent / THUMB_DIR_NAME / thumb_nombre
            thumb_rel = str(thumb_abs.relative_to(Path(GALLERY_ROOT).resolve()))

            archivos.append(EntradaArchivo(
                nombre=entrada.name,
                ruta_relativa=rel,
                tipo=tipo,
                extension=ext,
                tamanio=stat.st_size,
                modificado=stat.st_mtime,
                thumb_relativa=thumb_rel,
            ))

    return {
        "carpetas": carpetas,
        "archivos": archivos,
        "ruta_actual": ruta_relativa.strip("/"),
        "total": len(carpetas) + len(archivos),
    }


def _primer_archivo_en_carpeta(carpeta: Path) -> str:
    """
    Busca el primer archivo multimedia dentro de una carpeta (no recursivo)
    para usarlo como thumbnail de portada de la carpeta.
    Devuelve la ruta relativa a GALLERY_ROOT o cadena vacía si no hay archivos.
    """
    try:
        entradas = sorted(carpeta.iterdir(), key=lambda e: e.name.lower())
    except PermissionError:
        return ""

    raiz = Path(GALLERY_ROOT).resolve()
    for entrada in entradas:
        if entrada.is_file() and entrada.suffix.lower() in TODOS_LOS_FORMATOS:
            try:
                return str(entrada.relative_to(raiz))
            except ValueError:
                continue
    return ""


def info_archivo(ruta_relativa: str) -> dict:
    """
    Devuelve información básica de un archivo (nombre, tipo, tamaño, modificado).
    Valida que el archivo esté dentro de GALLERY_ROOT.
    """
    ruta_abs = _resolver_ruta_segura(ruta_relativa)

    if not ruta_abs.is_file():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta_abs}")

    stat = ruta_abs.stat()
    ext = ruta_abs.suffix.lower()

    return {
        "nombre": ruta_abs.name,
        "ruta_relativa": ruta_relativa,
        "tipo": _tipo_de_extension(ext),
        "extension": ext,
        "tamanio": stat.st_size,
        "modificado": stat.st_mtime,
        "modificado_legible": time.strftime(
            "%d/%m/%Y %H:%M", time.localtime(stat.st_mtime)
        ),
    }


def generar_breadcrumb(ruta_relativa: str) -> list[dict]:
    """
    Construye la lista de segmentos del breadcrumb para la navegación.
    Cada elemento: {'nombre': str, 'ruta': str}
    """
    partes = Path(ruta_relativa).parts
    crumbs = [{"nombre": "📁 Inicio", "ruta": ""}]
    acumulada = ""
    for parte in partes:
        acumulada = os.path.join(acumulada, parte)
        crumbs.append({"nombre": parte, "ruta": acumulada})
    return crumbs
