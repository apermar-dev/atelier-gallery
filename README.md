# Atelier Gallery

**Galería multimedia web ligera optimizada para Raspberry Pi y ARM64.**

Una solución frontend y backend sin complicaciones diseñada especialmente para servidores de bajos recursos que permite navegar directorios locales y visualizar imágenes (incluyendo HEIC y RAW) y vídeos generados al instante.

## Características principales
- **Backend asíncrono** con FastAPI + Uvicorn.
- **Generación de thumbnails on-the-fly:** Soporte para JPEG, PNG, WEBP, GIF, vídeo (FFmpeg), HEIC (pillow-heif) y RAW (rawpy).
- **Semáforo limitador de CPU:** Limita de forma segura la cantidad de conversiones en paralelo (ideal para la RPi).
- **Frontend sin dependencias** (Vanilla JS + CSS).
- **Lightbox adaptativo:** Soporta zoom/pan (gestos multitáctiles), deslizar para navegar e integración in-place para vídeos.
- **Protección contra path traversal.**

---

## 🚀 Guía de Despliegue en Raspberry Pi 4B

### Requisitos previos
- Raspberry Pi 4B con Ubuntu Server 24.04 LTS (ARM64)
- Acceso SSH a la Pi desde tu ordenador
- IP local de la Pi (ejemplo: `192.168.1.100`)

### 1. Transferir el proyecto a la Raspberry Pi

**Opción A — SCP (transferencia directa)**
```bash
# Desde tu ordenador, en el directorio donde está el proyecto:
scp -r "visualizador de imagenes/" ubuntu@192.168.1.100:/opt/atelier/gallery
```

**Opción B — Git (recomendado)**
```bash
# En la Raspberry Pi:
sudo mkdir -p /opt/atelier/gallery
sudo chown ubuntu:ubuntu /opt/atelier
git clone https://github.com/apermar-dev/atelier-gallery.git /opt/atelier/gallery
```

---

### 2. Instalar dependencias en la Raspberry Pi

```bash
# Conectar por SSH a la Pi
ssh ubuntu@192.168.1.100

# Ir al directorio del proyecto
cd /opt/atelier/gallery

# Dar permisos de ejecución al script
chmod +x install.sh

# Ejecutar la instalación (puede tardar 5-10 min en ARM64)
./install.sh
```

> **Nota:** La primera instalación de `pillow-heif` y `rawpy` puede tardar varios minutos porque compilan desde fuente en ARM64.

---

### 3. Instalar el servicio systemd

```bash
# Copiar el unit file al directorio de systemd
sudo cp /opt/atelier/gallery/gallery.service /etc/systemd/system/atelier-gallery.service

# Recargar la configuración de systemd
sudo systemctl daemon-reload

# Habilitar el servicio para que arranque automáticamente al iniciar la Pi
sudo systemctl enable atelier-gallery

# Arrancar el servicio ahora
sudo systemctl start atelier-gallery

# Verificar que está corriendo
sudo systemctl status atelier-gallery
```

La salida debe mostrar **`active (running)`** en verde.

---

### 4. Verificar la instalación y acceder

Desde tu ordenador o teléfono móvil conectado a la misma red Wi-Fi, abre el navegador y accede a:
```
http://TU_IP_RASPBERRY:8080
```
*(Ejemplo: `http://192.168.1.100:8080`)*

---

### 5. Configurar la ruta de las fotos

Por defecto, la galería busca las fotos en:
```
/opt/atelier/files/photos/
```

Puedes organizarlo en subcarpetas libremente y los *thumbnails* se generarán automáticamente en el fondo (dentro de una carpeta ocaída `.thumbnails/`) la primera vez que entres en ellas.

*(Si deseas cambiar esta ruta, edita la variable `GALLERY_ROOT` en `config.py` y reinicia el servicio).*

---

### 6. Actualizar el código

```bash
cd /opt/atelier/gallery
git pull
sudo systemctl restart atelier-gallery
```

---

### Diagnóstico rápido

```bash
# Ver logs en tiempo real para descartar errores del servidor
sudo journalctl -u atelier-gallery -f

# Ver el registro de conversiones de thumbnails incorrectas
tail -f /opt/atelier/gallery/thumbnail_errors.log
```
