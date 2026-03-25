#!/bin/bash

# Script de instalación para Galería Multimedia Ligera
# Entorno: Ubuntu Server 24.04 LTS (ARM64) - Raspberry Pi 4B

set -e # Detener ejecución ante cualquier error

echo "--- Iniciando instalación de dependencias de sistema ---"
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg libheif-dev libraw-dev exiftool

echo "--- Preparando entorno virtual Python ---"
python3 -m venv venv
source venv/bin/activate

echo "--- Instalando dependencias de Python (esto puede tardar en ARM64) ---"
pip install --upgrade pip
pip install -r requirements.txt

echo "--- Creando directorios y ajustando permisos ---"
# Creamos la ruta raíz si no existe (solo para test local, normalmente ya existe)
sudo mkdir -p /opt/atelier/files/photos
sudo chown -R $USER:$USER /opt/atelier/files/photos

# Creamos archivo de logs de thumbnails
touch thumbnail_errors.log
chmod 664 thumbnail_errors.log

echo "--- Instalación completada ---"
echo "Ejecuta 'source venv/bin/activate && python3 main.py' para probar."
