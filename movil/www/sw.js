// Service worker de la app web: guarda los archivos para que abra sin internet.
// Al cambiar cualquier archivo de la app, subí la versión para que se actualice.
const VERSION = 'pato-v3';
const ARCHIVOS = [
  './', 'index.html', 'estilos.css', 'app.js', 'alarmas.js', 'manifest.webmanifest',
  'iconos/icono-180.png', 'iconos/icono-192.png', 'iconos/icono-512.png',
];

self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(ARCHIVOS)));
  self.skipWaiting();
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(caches.keys().then((claves) =>
    Promise.all(claves.filter((c) => c !== VERSION).map((c) => caches.delete(c)))));
  self.clients.claim();
});

// Primero la red (para recibir actualizaciones); sin conexión, lo guardado.
self.addEventListener('fetch', (evento) => {
  const url = new URL(evento.request.url);
  if (evento.request.method !== 'GET' || url.origin !== self.location.origin) return;
  evento.respondWith(
    fetch(evento.request)
      .then((respuesta) => {
        const copia = respuesta.clone();
        caches.open(VERSION).then((cache) => cache.put(evento.request, copia));
        return respuesta;
      })
      .catch(() => caches.match(evento.request)),
  );
});
