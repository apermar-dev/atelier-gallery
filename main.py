"""
main.py — FastAPI application: rutas principales, middleware y BackgroundTasks.
Sirve la galería multimedia con navegación de archivos, thumbnails y API JSON.
"""
import os
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Response
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware

from config import (
    GALLERY_ROOT,
    HOST,
    PORT,
    CACHE_MAX_AGE,
    FORMATOS_VIDEO,
)
from scanner import listar_directorio, info_archivo, generar_breadcrumb
from thumbnail import (
    generar_thumbnail,
    thumbnail_existe,
    ruta_thumbnail,
    convertir_heic_a_jpeg,
    duracion_video,
)

# Inicialización de la app
app = FastAPI(
    title="Galería Multimedia",
    description="Galería web ligera para Raspberry Pi",
    version="1.0.0",
    docs_url=None,  # Desactivar Swagger UI en producción
    redoc_url=None,
)

# Middleware de compresión gzip para respuestas HTTP
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Archivos estáticos y templates de Jinja2
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Ruta absoluta de GALLERY_ROOT para comprobaciones de seguridad
_GALLERY_ROOT_ABS = Path(GALLERY_ROOT).resolve()

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _validar_ruta(ruta_relativa: str) -> Path:
    """
    Valida y resuelve una ruta relativa dentro de GALLERY_ROOT.
    Lanza HTTPException 403 si se detecta path traversal.
    """
    try:
        destino = (_GALLERY_ROOT_ABS / ruta_relativa).resolve()
        destino.relative_to(_GALLERY_ROOT_ABS)
        return destino
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado: ruta fuera de la galería.")


def _headers_cache(max_age: int = CACHE_MAX_AGE) -> dict:
    """Genera headers de caché para respuestas de archivos estáticos y thumbnails."""
    return {"Cache-Control": f"public, max-age={max_age}"}


# --------------------------------------------------------------------------
# Rutas de navegación
# --------------------------------------------------------------------------

@app.get("/", response_class=RedirectResponse)
async def raiz():
    """Redirige la raíz a /browse/ (inicio de la galería)."""
    return RedirectResponse(url="/browse/")


@app.get("/browse/{ruta_relativa:path}", response_class=HTMLResponse)
async def browse(request: Request, ruta_relativa: str = ""):
    """
    Renderiza la vista de galería para una carpeta dada.
    Muestra subcarpetas al inicio, luego archivos multimedia paginados.
    """
    ruta_abs = _validar_ruta(ruta_relativa)

    if not ruta_abs.exists():
        return templates.TemplateResponse("error.html", {
            "request": request,
            "codigo": 404,
            "mensaje": f"El directorio '{ruta_relativa}' no existe.",
        }, status_code=404)

    if not ruta_abs.is_dir():
        raise HTTPException(status_code=400, detail="La ruta no es un directorio.")

    try:
        contenido = listar_directorio(ruta_relativa)
    except PermissionError:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "codigo": 403,
            "mensaje": "Sin permisos para acceder a este directorio.",
        }, status_code=403)

    # Paginación: máximo 100 items por página
    pagina = int(request.query_params.get("p", 1))
    por_pagina = 100
    archivos_todos = contenido["archivos"]
    inicio = (pagina - 1) * por_pagina
    archivos_pagina = archivos_todos[inicio: inicio + por_pagina]
    total_paginas = max(1, -(-len(archivos_todos) // por_pagina))  # ceil division

    breadcrumb = generar_breadcrumb(ruta_relativa)

    # Construir ruta del nivel superior
    ruta_padre = str(Path(ruta_relativa).parent) if ruta_relativa else None
    if ruta_padre == ".":
        ruta_padre = ""

    return templates.TemplateResponse("gallery.html", {
        "request": request,
        "carpetas": contenido["carpetas"],
        "archivos": archivos_pagina,
        "ruta_actual": ruta_relativa,
        "ruta_padre": ruta_padre,
        "breadcrumb": breadcrumb,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "total_archivos": len(archivos_todos),
    })


# --------------------------------------------------------------------------
# Rutas de thumbnails
# --------------------------------------------------------------------------

# Placeholder SVG para cuando el thumbnail aún no está generado
_PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">
  <rect width="320" height="320" fill="#1e1e2e"/>
  <circle cx="160" cy="140" r="40" fill="#313244"/>
  <rect x="80" y="200" width="160" height="12" rx="6" fill="#313244"/>
  <rect x="110" y="222" width="100" height="10" rx="5" fill="#45475a"/>
</svg>"""

_PLACEHOLDER_BYTES = _PLACEHOLDER_SVG.encode()


@app.get("/thumb/{ruta_relativa:path}")
async def thumb(ruta_relativa: str, background_tasks: BackgroundTasks):
    """
    Devuelve el thumbnail de un archivo.
    Si no existe: responde inmediatamente con un SVG placeholder y
    lanza la generación en background (BackgroundTasks de FastAPI).
    """
    ruta_abs = _validar_ruta(ruta_relativa)

    if not ruta_abs.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    thumb_path = ruta_thumbnail(ruta_abs)

    if thumb_path.exists():
        # Thumbnail ya existe: devolverlo directamente con headers de caché
        return FileResponse(
            thumb_path,
            media_type="image/jpeg",
            headers=_headers_cache(),
        )

    # Lanzar generación en background y devolver placeholder
    background_tasks.add_task(generar_thumbnail, ruta_abs)

    return Response(
        content=_PLACEHOLDER_BYTES,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


# --------------------------------------------------------------------------
# Ruta para servir archivos originales
# --------------------------------------------------------------------------

@app.get("/raw/{ruta_relativa:path}")
async def raw(ruta_relativa: str):
    """
    Sirve el archivo original al navegador.
    Para archivos HEIC: convierte a JPEG on-the-fly (los navegadores no lo soportan).
    Para vídeos: permite streaming con soporte de range requests.
    """
    ruta_abs = _validar_ruta(ruta_relativa)

    if not ruta_abs.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    ext = ruta_abs.suffix.lower()

    # Conversión on-the-fly de HEIC a JPEG para el lightbox
    if ext in {'.heic', '.heif'}:
        jpeg_bytes = await convertir_heic_a_jpeg(ruta_abs)
        if jpeg_bytes is None:
            raise HTTPException(status_code=500, detail="Error al convertir HEIC.")
        return Response(
            content=jpeg_bytes,
            media_type="image/jpeg",
            headers=_headers_cache(3600),  # 1 hora de caché para conversiones
        )

    # Para vídeos y el resto de archivos: FileResponse con soporte de ranges
    media_type, _ = mimetypes.guess_type(str(ruta_abs))
    media_type = media_type or "application/octet-stream"

    return FileResponse(
        ruta_abs,
        media_type=media_type,
        headers=_headers_cache(),
    )


# --------------------------------------------------------------------------
# API JSON
# --------------------------------------------------------------------------

@app.get("/api/ls/{ruta_relativa:path}")
async def api_ls(ruta_relativa: str = ""):
    """Devuelve el contenido de un directorio en formato JSON."""
    _validar_ruta(ruta_relativa)
    try:
        contenido = listar_directorio(ruta_relativa)
        return JSONResponse(content=contenido)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@app.get("/api/meta/{ruta_relativa:path}")
async def api_meta(ruta_relativa: str):
    """
    Devuelve metadatos EXIF/mediainfo de un archivo.
    Usa exiftool si está disponible; si no, devuelve metadatos básicos del FS.
    """
    ruta_abs = _validar_ruta(ruta_relativa)

    if not ruta_abs.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    info = info_archivo(ruta_relativa)
    ext = ruta_abs.suffix.lower()
    exif_data = {}

    # Intentar extraer EXIF via exiftool (herramienta de sistema independiente)
    try:
        import subprocess, json
        proc = subprocess.run(
            ["exiftool", "-json", "-charset", "utf8", str(ruta_abs)],
            capture_output=True, timeout=10, text=True
        )
        if proc.returncode == 0:
            datos = json.loads(proc.stdout)
            if datos:
                raw_exif = datos[0]
                # Filtrar campos útiles para el panel lateral
                campos_utiles = [
                    "DateTimeOriginal", "CreateDate", "Make", "Model",
                    "LensModel", "ExposureTime", "FNumber", "ISO",
                    "ImageWidth", "ImageHeight", "GPSLatitude", "GPSLongitude",
                    "Duration", "VideoFrameRate", "AudioBitrate",
                ]
                exif_data = {k: raw_exif[k] for k in campos_utiles if k in raw_exif}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        # exiftool no disponible o timeout: continuamos sin EXIF
        pass

    # Duración para vídeos
    duracion = None
    if ext in FORMATOS_VIDEO:
        duracion = await duracion_video(ruta_abs)

    return JSONResponse(content={
        **info,
        "exif": exif_data,
        "duracion": duracion,
    })


# --------------------------------------------------------------------------
# Manejo de errores globales
# --------------------------------------------------------------------------

@app.exception_handler(404)
async def handler_404(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "codigo": 404,
        "mensaje": "Página o recurso no encontrado.",
    }, status_code=404)


@app.exception_handler(500)
async def handler_500(request: Request, exc: Exception):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "codigo": 500,
        "mensaje": "Error interno del servidor.",
    }, status_code=500)


# --------------------------------------------------------------------------
# Entrada directa (para desarrollo local)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,  # Desactivar reload en producción RPi
        workers=1,     # Un solo worker para RPi — async maneja la concurrencia
    )
