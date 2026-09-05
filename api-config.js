(function () {
  'use strict';
  if (window.MEDIRAG_API_BASE_URL) return;
  const local = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  window.MEDIRAG_API_BASE_URL = local
    ? 'http://127.0.0.1:8000'
    : 'https://tcm-multi-agent-rag-api.onrender.com';
})();
