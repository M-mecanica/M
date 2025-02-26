// Nome do cache (pode incluir versão para facilitar updates)
const CACHE_NAME = 'm-pwa-cache-v1';

// Liste aqui os recursos que deseja pré-cachear.
// Você pode adicionar ou remover conforme sua aplicação evolui.
const PRECACHE_URLS = [
  '/',                        // página inicial
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/images/logo_m_transparente.png',
  // Adicione outras imagens, fontes ou páginas se desejar
];

self.addEventListener('install', (event) => {
  // Evento disparado na instalação do SW (pré-cache de recursos)
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
});

self.addEventListener('activate', (event) => {
  // Limpar caches antigos se houver mudança de versão
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

self.addEventListener('fetch', (event) => {
  // Estratégia de cache: "Cache, falling back to network"
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      // Se encontrar no cache, retorna. Senão, busca na rede.
      return cachedResponse || fetch(event.request);
    })
  );
});
