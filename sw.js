const CACHE_NAME = 'zerkalo-v1';
const urlsToCache = [
  '/webapp',
  '/webapp/index.html',
  '/public/manifest.json',
  '/icons/android/icon-192.png',
  '/icons/android/icon-512.png'
];

// Устанавливаем кэш
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// Отвечаем из кэша
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});

// Обновляем кэш
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
