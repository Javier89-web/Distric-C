{% load static %}
const CACHE_NAME = "districc-pwa-v15-home-design";

// La aplicación necesita internet para mapas, tráfico, clima y demás APIs.
// Solo se guardan recursos estáticos de interfaz; nunca páginas, formularios,
// rutas, datos GPS ni respuestas de API.
const STATIC_ASSETS = [
  "{% static 'css/base/usuario.css' %}",
  "{% static 'css/base/administrador.css' %}",
  "{% static 'css/base/branding.css' %}",
  "{% static 'js/base/usuario.js' %}",
  "{% static 'js/base/administrador.js' %}",
  "{% static 'js/base/tab_lock.js' %}",
  "{% static 'js/base/single_submit.js' %}",
  "{% static 'img/branding/distric-c-logo.png' %}",
  "{% static 'icons/distric-favicon.png' %}",
  "{% static 'icons/icon-192x192.png' %}",
  "{% static 'icons/icon-512x512.png' %}"
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => Promise.all(
      names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  // Todo lo dinámico y todo recurso externo depende de la red.
  if (url.origin !== self.location.origin || !url.pathname.startsWith("/static/")) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return response;
      });
    })
  );
});
