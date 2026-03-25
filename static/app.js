/**
 * app.js — Lógica frontend: Lightbox, Lazy Loading, Skeleton, Swipe táctil.
 * Vanilla JS puro, sin dependencias externas.
 */

"use strict";

/* ══════════════════════════════════════════════════════════
   CONSTANTES Y ESTADO GLOBAL
   ══════════════════════════════════════════════════════════ */

/** Lista de items multimedia de la página, construida al cargar. */
let ITEMS = [];
/** Índice del item actualmente abierto en el lightbox. */
let currentIdx = -1;
/** Si el lightbox está abierto. */
let lbOpen = false;

/* ══════════════════════════════════════════════════════════
   LAZY LOADING + SKELETON LOADER
   ══════════════════════════════════════════════════════════ */

/**
 * Inicializa el IntersectionObserver para lazy loading de thumbnails.
 * Cuando una imagen entra en el viewport se establece el src real
 * y se elimina el skeleton cuando carga.
 */
function initLazyLoading() {
  const thumbs = document.querySelectorAll('.media-thumb');
  if (!thumbs.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const img = entry.target;
      const src = img.dataset.src;
      if (!src) return;

      img.src = src;

      img.addEventListener('load', () => {
        img.classList.add('visible');
        // Ocultar el skeleton cuando la imagen está lista
        const skeleton = img.parentElement.querySelector('.skeleton');
        if (skeleton) skeleton.classList.add('loaded');
        // Relanzar solicitud si recibimos SVG placeholder (thumbnail aún generándose)
        if (img.naturalWidth < 10) {
          setTimeout(() => {
            img.src = src + '?r=' + Date.now();
          }, 2000);
        }
      }, { once: true });

      img.addEventListener('error', () => {
        // Mostrar el icono de error del tipo de archivo
        const errIcon = img.parentElement.querySelector('.media-error-icon');
        if (errIcon) errIcon.style.display = '';
        const skeleton = img.parentElement.querySelector('.skeleton');
        if (skeleton) skeleton.classList.add('loaded');
      }, { once: true });

      observer.unobserve(img);
    });
  }, { rootMargin: '200px' });

  thumbs.forEach(img => observer.observe(img));
}

/* ══════════════════════════════════════════════════════════
   LIGHTBOX
   ══════════════════════════════════════════════════════════ */

const lb          = document.getElementById('lightbox');
const lbWrap      = document.getElementById('lb-media-wrap');
const lbOverlay   = document.getElementById('lb-overlay');
const lbClose     = document.getElementById('lb-close');
const lbPrev      = document.getElementById('lb-prev');
const lbNext      = document.getElementById('lb-next');
const lbInfoPanel = document.getElementById('lb-info-panel');
const lbInfoToggle= document.getElementById('lb-info-toggle');
const lbFilename  = document.getElementById('lb-filename');
const lbMetaList  = document.getElementById('lb-meta-list');

/** Construye la lista de items desde los article.media-card del DOM. */
function buildItemList() {
  ITEMS = Array.from(document.querySelectorAll('.media-card')).map(card => ({
    ruta:    card.dataset.ruta,
    tipo:    card.dataset.tipo,
    ext:     card.dataset.ext,
    nombre:  card.dataset.nombre,
    idx:     Number(card.dataset.idx),
  }));
}

/** Abre el lightbox con el item en la posición dada. */
function openLightbox(idx) {
  if (idx < 0 || idx >= ITEMS.length) return;
  currentIdx = idx;
  lbOpen = true;

  lb.hidden = false;
  document.body.style.overflow = 'hidden';

  renderLightboxMedia(ITEMS[idx]);
  updateURL(ITEMS[idx].ruta);
}

/** Cierra el lightbox y libera recursos. */
function closeLightbox() {
  if (!lbOpen) return;
  lbOpen = false;
  lb.hidden = true;
  document.body.style.overflow = '';

  // Pausar vídeo si estaba reproduciendo
  const video = lbWrap.querySelector('video');
  if (video) video.pause();

  lbWrap.innerHTML = '';
  lbFilename.textContent = '—';
  lbMetaList.innerHTML = '';
  lbInfoPanel.classList.remove('open');

  history.replaceState(null, '', window.location.pathname + window.location.search);
}

/** Navega al item anterior o siguiente. */
function navigateLightbox(dir) {
  const newIdx = currentIdx + dir;
  if (newIdx < 0 || newIdx >= ITEMS.length) return;

  // Pausar vídeo actual
  const video = lbWrap.querySelector('video');
  if (video) video.pause();

  openLightbox(newIdx);
}

/**
 * Renderiza el media (imagen o vídeo) en el lightbox.
 * Para images: con zoom via CSS transform y pan con drag.
 * Para vídeos: player HTML5 nativo con autoplay.
 */
function renderLightboxMedia(item) {
  lbWrap.innerHTML = '';
  lbFilename.textContent = item.nombre;
  lbMetaList.innerHTML = '<dt>Cargando metadatos…</dt>';

  // Spinner de carga
  const spinner = document.createElement('div');
  spinner.className = 'lb-spinner';
  lbWrap.appendChild(spinner);

  const isVideo = item.tipo === 'video';
  const rawUrl  = `/raw/${item.ruta}`;

  if (isVideo) {
    const video = document.createElement('video');
    video.controls = true;
    video.autoplay = true;
    video.preload  = 'auto';
    video.style.display = 'none';

    const source = document.createElement('source');
    source.src = rawUrl;
    video.appendChild(source);

    video.addEventListener('loadedmetadata', () => {
      spinner.remove();
      video.style.display = '';
    }, { once: true });

    video.addEventListener('error', () => {
      spinner.remove();
      const msg = document.createElement('p');
      msg.textContent = 'Error al reproducir el vídeo.';
      msg.style.color = 'var(--text-muted)';
      lbWrap.appendChild(msg);
    }, { once: true });

    lbWrap.appendChild(video);

  } else {
    const img = document.createElement('img');
    img.alt   = item.nombre;
    img.style.display = 'none';

    img.addEventListener('load', () => {
      spinner.remove();
      img.style.display = '';
      initZoomPan(img);
    }, { once: true });

    img.addEventListener('error', () => {
      spinner.remove();
      const msg = document.createElement('p');
      msg.textContent = 'No se pudo cargar la imagen.';
      msg.style.color = 'var(--text-muted)';
      lbWrap.appendChild(msg);
    }, { once: true });

    img.src = rawUrl;
    lbWrap.appendChild(img);
  }

  // Cargar metadatos asíncronamente
  fetchMeta(item.ruta);
}

/** Actualiza el hash de la URL con la ruta del asset actual (deep link). */
function updateURL(ruta) {
  const url = new URL(window.location.href);
  url.hash = encodeURIComponent(ruta);
  history.replaceState(null, '', url.toString());
}

/* ── Metadatos EXIF ──────────────────────────────────────── */
const ETIQUETAS = {
  DateTimeOriginal: '📅 Fecha',
  CreateDate:       '📅 Creación',
  Make:             '📷 Marca',
  Model:            '📷 Modelo',
  LensModel:        '🔭 Objetivo',
  ExposureTime:     '⏱ Exposición',
  FNumber:          '🔆 Apertura',
  ISO:              '📡 ISO',
  ImageWidth:       '↔ Ancho',
  ImageHeight:      '↕ Alto',
  GPSLatitude:      '📍 Latitud',
  GPSLongitude:     '📍 Longitud',
  Duration:         '⏳ Duración',
  VideoFrameRate:   '🎞 FPS',
};

async function fetchMeta(ruta) {
  try {
    const resp = await fetch(`/api/meta/${ruta}`);
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();

    const dl = document.createElement('dl');

    // Datos básicos del sistema de archivos
    const camposSistema = [
      ['📁 Archivo', data.nombre],
      ['📏 Tamaño',  formatBytes(data.tamanio)],
      ['🕐 Modificado', data.modificado_legible],
    ];
    if (data.duracion) camposSistema.push(['⏳ Duración', data.duracion]);

    camposSistema.forEach(([k, v]) => appendMeta(dl, k, v));

    // Datos EXIF
    if (data.exif && Object.keys(data.exif).length > 0) {
      const sep = document.createElement('dt');
      sep.textContent = '— EXIF —';
      sep.style.marginTop = '20px';
      dl.appendChild(sep);

      Object.entries(data.exif).forEach(([k, v]) => {
        appendMeta(dl, ETIQUETAS[k] || k, v);
      });
    }

    lbMetaList.replaceWith(dl);
    dl.id = 'lb-meta-list';

  } catch (err) {
    lbMetaList.innerHTML = '<dt>No disponible</dt>';
  }
}

function appendMeta(dl, key, value) {
  const dt = document.createElement('dt');
  dt.textContent = key;
  const dd = document.createElement('dd');
  dd.textContent = value;
  dl.appendChild(dt);
  dl.appendChild(dd);
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

/* ── Zoom y Pan en imágenes ─────────────────────────────── */
function initZoomPan(img) {
  let scale = 1;
  let originX = 0;
  let originY = 0;
  let isDragging = false;
  let startX = 0, startY = 0;
  let currentX = 0, currentY = 0;

  const setTransform = () => {
    img.style.transform = `scale(${scale}) translate(${currentX}px, ${currentY}px)`;
  };

  // Doble clic: zoom in/out
  img.addEventListener('dblclick', (e) => {
    scale = scale === 1 ? 2.5 : 1;
    currentX = currentY = 0;
    setTransform();
  });

  // Rueda del ratón: zoom suave
  img.addEventListener('wheel', (e) => {
    e.preventDefault();
    scale = Math.min(6, Math.max(1, scale - e.deltaY * 0.002));
    if (scale === 1) { currentX = currentY = 0; }
    setTransform();
  }, { passive: false });

  // Drag para pan
  img.addEventListener('mousedown', (e) => {
    if (scale === 1) return;
    isDragging = true;
    img.classList.add('grabbing');
    startX = e.clientX - currentX;
    startY = e.clientY - currentY;
  });
  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    currentX = e.clientX - startX;
    currentY = e.clientY - startY;
    setTransform();
  });
  document.addEventListener('mouseup', () => {
    isDragging = false;
    img.classList.remove('grabbing');
  });

  // Pinch zoom táctil
  let lastPinchDist = 0;
  img.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) {
      lastPinchDist = getPinchDist(e);
    } else if (e.touches.length === 1 && scale > 1) {
      isDragging = true;
      startX = e.touches[0].clientX - currentX;
      startY = e.touches[0].clientY - currentY;
    }
  }, { passive: true });

  img.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const dist = getPinchDist(e);
      const ratio = dist / lastPinchDist;
      scale = Math.min(6, Math.max(1, scale * ratio));
      lastPinchDist = dist;
      if (scale === 1) { currentX = currentY = 0; }
      setTransform();
    } else if (isDragging && e.touches.length === 1) {
      currentX = e.touches[0].clientX - startX;
      currentY = e.touches[0].clientY - startY;
      setTransform();
    }
  }, { passive: false });

  img.addEventListener('touchend', () => { isDragging = false; });
}

function getPinchDist(e) {
  const [a, b] = e.touches;
  return Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
}

/* ── Swipe táctil en el lightbox ────────────────────────── */
function initSwipe() {
  let touchStartX = 0;
  lb.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) touchStartX = e.touches[0].clientX;
  }, { passive: true });

  lb.addEventListener('touchend', (e) => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 60) {
      navigateLightbox(dx < 0 ? 1 : -1);
    }
  }, { passive: true });
}

/* ══════════════════════════════════════════════════════════
   EVENTOS DEL LIGHTBOX
   ══════════════════════════════════════════════════════════ */

function bindLightboxEvents() {
  // Clicks en tarjetas multimedia
  document.getElementById('media-grid')?.addEventListener('click', (e) => {
    const card = e.target.closest('.media-card');
    if (!card) return;
    openLightbox(Number(card.dataset.idx));
  });

  // Teclado en tarjetas (accesibilidad)
  document.getElementById('media-grid')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const card = e.target.closest('.media-card');
      if (card) { e.preventDefault(); openLightbox(Number(card.dataset.idx)); }
    }
  });

  // Controles del lightbox
  lbClose.addEventListener('click', closeLightbox);
  lbOverlay.addEventListener('click', closeLightbox);
  lbPrev.addEventListener('click', () => navigateLightbox(-1));
  lbNext.addEventListener('click', () => navigateLightbox(1));

  // Panel de info
  lbInfoToggle.addEventListener('click', () => {
    lbInfoPanel.classList.toggle('open');
  });

  // Teclado global
  document.addEventListener('keydown', (e) => {
    if (!lbOpen) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft')  navigateLightbox(-1);
    if (e.key === 'ArrowRight') navigateLightbox(1);
  });

  // Swipe táctil
  initSwipe();
}

/* ══════════════════════════════════════════════════════════
   DEEP LINK: abrir directamente desde hash en la URL
   ══════════════════════════════════════════════════════════ */

function checkDeepLink() {
  const hash = decodeURIComponent(window.location.hash.slice(1));
  if (!hash) return;
  const idx = ITEMS.findIndex(it => it.ruta === hash);
  if (idx !== -1) openLightbox(idx);
}

/* ══════════════════════════════════════════════════════════
   INICIALIZACIÓN
   ══════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  initLazyLoading();
  buildItemList();
  bindLightboxEvents();
  checkDeepLink();
});
