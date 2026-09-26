/* Service Worker de Kiki App.

   - Estáticos: cache-first (la PWA arranca al instante y sin red).
   - Navegación y API GET: network-first con copia en caché de respaldo.
   - Escrituras: pasan directas; si fallan, mobile.js las encola en el cliente. */

const VERSION = 'kiki-v1';
const CACHE_SHELL = `${VERSION}-shell`;
const CACHE_DATOS = `${VERSION}-datos`;

const SHELL = [
  '/m',
  '/static/css/app.css',
  '/static/js/core.js',
  '/static/js/mobile.js',
  '/static/vendor/alpine.min.js',
  '/static/icons/favicon.svg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/manifest.webmanifest',
];

self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches
      .open(CACHE_SHELL)
      // addAll es atómico: si un recurso falla, no se instala nada. Se añaden
      // de uno en uno para que un 404 puntual no deje la PWA sin caché.
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((claves) =>
        Promise.all(
          claves
            .filter((clave) => !clave.startsWith(VERSION))
            .map((clave) => caches.delete(clave))
        )
      )
      .then(() => self.clients.claim())
  );
});

async function redPrimero(peticion, nombreCache) {
  const cache = await caches.open(nombreCache);
  try {
    const respuesta = await fetch(peticion);
    if (respuesta && respuesta.ok) cache.put(peticion, respuesta.clone());
    return respuesta;
  } catch (error) {
    const guardada = await cache.match(peticion);
    if (guardada) return guardada;
    throw error;
  }
}

async function cachePrimero(peticion) {
  const cache = await caches.open(CACHE_SHELL);
  const guardada = await cache.match(peticion);
  if (guardada) {
    // Refresco en segundo plano: la próxima visita ya tiene la versión nueva.
    fetch(peticion)
      .then((respuesta) => respuesta.ok && cache.put(peticion, respuesta.clone()))
      .catch(() => null);
    return guardada;
  }
  const respuesta = await fetch(peticion);
  if (respuesta && respuesta.ok) cache.put(peticion, respuesta.clone());
  return respuesta;
}

self.addEventListener('fetch', (evento) => {
  const peticion = evento.request;
  if (peticion.method !== 'GET') return;

  const url = new URL(peticion.url);
  if (url.origin !== self.location.origin) return;

  if (peticion.mode === 'navigate') {
    evento.respondWith(
      redPrimero(peticion, CACHE_SHELL).catch(() => caches.match('/m'))
    );
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    evento.respondWith(redPrimero(peticion, CACHE_DATOS));
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    evento.respondWith(cachePrimero(peticion));
  }
});
