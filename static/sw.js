const CACHE_NAME = 'africanaai-pwa-v1';
const CORE_ASSETS = [
  '/',
  '/social/',
  '/users/profile/',
  '/eshop/',
  '/languages/',
  '/hotel/',
  '/movie/',
  '/static/manifest.webmanifest',
  '/static/images/africana-ai-logo.svg',
  '/static/robots.txt'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);

    if (event.request.destination === 'document' || event.request.headers.get('accept')?.includes('text/html')) {
      try {
        const response = await fetch(event.request);
        cache.put(event.request, response.clone());
        return response;
      } catch (err) {
        const cached = await cache.match(event.request);
        return cached || await cache.match('/');
      }
    }

    const cachedResponse = await cache.match(event.request);
    if (cachedResponse) {
      return cachedResponse;
    }

    try {
      const response = await fetch(event.request);
      if (response && response.status === 200 && response.type !== 'opaque') {
        cache.put(event.request, response.clone());
      }
      return response;
    } catch (err) {
      return cachedResponse;
    }
  })());
});
