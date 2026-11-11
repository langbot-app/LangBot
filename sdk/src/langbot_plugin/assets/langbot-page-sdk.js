/**
 * LangBot Plugin Page SDK
 *
 * This script provides a bridge between plugin pages (running in iframes)
 * and the LangBot host application.
 *
 * Features:
 * - Automatic dark/light theme synchronization
 * - Language/locale information
 * - Automatic i18n loading from i18n/{locale}.json files
 * - API calls to the plugin backend (handle_page_api)
 *
 * Usage in your HTML page:
 *   <script src="/api/v1/plugins/_sdk/page-sdk.js"></script>
 *   <script>
 *     langbot.onReady(async (ctx) => {
 *       console.log('Theme:', ctx.theme);      // 'light' or 'dark'
 *       console.log('Language:', ctx.language); // 'zh-Hans', 'en-US', etc.
 *       console.log(langbot.t('title'));        // Translated string
 *
 *       // Call your plugin's handle_page_api
 *       const result = await langbot.api('/my-endpoint', { key: 'value' });
 *     });
 *   </script>
 *
 * i18n: Place JSON files in an i18n/ directory next to your HTML:
 *   pages/dashboard/
 *     index.html
 *     i18n/
 *       en_US.json     (fallback)
 *       zh_Hans.json
 *
 * Elements with data-i18n="key" will be auto-translated.
 */
(function () {
  'use strict';

  var _theme = 'light';
  var _language = 'en-US';
  var _ready = false;
  var _readyCallbacks = [];
  var _themeCallbacks = [];
  var _pendingRequests = {};
  var _requestIdCounter = 0;
  var _translations = {};
  var _i18nLoaded = false;
  var _languageCallbacks = [];
  var _i18nPromise = null;

  // Apply theme to document
  function applyTheme(theme) {
    _theme = theme;
    var root = document.documentElement;
    root.classList.remove('light', 'dark');
    root.classList.add(theme);
    root.setAttribute('data-theme', theme);

    // Set CSS custom properties for common dark/light patterns
    if (theme === 'dark') {
      root.style.setProperty('--langbot-bg', '#0a0a0a');
      root.style.setProperty('--langbot-bg-card', '#171717');
      root.style.setProperty('--langbot-text', '#fafafa');
      root.style.setProperty('--langbot-text-muted', '#a1a1aa');
      root.style.setProperty('--langbot-border', '#27272a');
      root.style.setProperty('--langbot-accent', '#3b82f6');
    } else {
      root.style.setProperty('--langbot-bg', '#ffffff');
      root.style.setProperty('--langbot-bg-card', '#f8fafc');
      root.style.setProperty('--langbot-text', '#0a0a0a');
      root.style.setProperty('--langbot-text-muted', '#71717a');
      root.style.setProperty('--langbot-border', '#e4e4e7');
      root.style.setProperty('--langbot-accent', '#2563eb');
    }

    for (var i = 0; i < _themeCallbacks.length; i++) {
      try { _themeCallbacks[i](theme); } catch (e) { console.error(e); }
    }
  }

  // Convert language code for i18n filenames: "zh-Hans" → "zh_Hans"
  function langToFileName(lang) {
    return lang.replace(/-/g, '_');
  }

  // Load i18n JSON from ./i18n/{locale}.json relative to the page
  function loadI18n(lang) {
    var fileName = langToFileName(lang);
    return fetch('./i18n/' + fileName + '.json')
      .then(function (resp) {
        if (resp.ok) return resp.json();
        // Fallback to en_US
        if (fileName !== 'en_US') {
          return fetch('./i18n/en_US.json').then(function (r) {
            return r.ok ? r.json() : {};
          });
        }
        return {};
      })
      .then(function (data) {
        _translations = data || {};
        _i18nLoaded = true;
        applyTranslations();
        return _translations;
      })
      .catch(function () {
        _translations = {};
        _i18nLoaded = true;
      });
  }

  // Allowed attributes for data-i18n-attr (whitelist to prevent XSS)
  var SAFE_I18N_ATTRS = ['placeholder', 'title', 'alt', 'aria-label', 'aria-description'];

  // Apply translations to elements with data-i18n attribute
  function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      if (_translations[key] != null) {
        // Support data-i18n-attr for safe attribute translation (e.g. placeholder)
        var attr = el.getAttribute('data-i18n-attr');
        if (attr && SAFE_I18N_ATTRS.indexOf(attr) !== -1) {
          el.setAttribute(attr, _translations[key]);
        } else {
          el.textContent = _translations[key];
        }
      }
    });
  }

  // Listen for messages from the parent LangBot page
  window.addEventListener('message', function (event) {
    var data = event.data;
    if (!data || typeof data !== 'object') return;

    if (data.type === 'langbot:context') {
      var oldTheme = _theme;
      var oldLang = _language;
      _language = data.language || _language;

      applyTheme(data.theme || 'light');

      if (!_ready) {
        // Load i18n before marking ready and firing callbacks
        _i18nPromise = loadI18n(_language).then(function () {
          _ready = true;
          var ctx = { theme: _theme, language: _language };
          for (var i = 0; i < _readyCallbacks.length; i++) {
            try { _readyCallbacks[i](ctx); } catch (e) { console.error(e); }
          }
        });
      } else {
        // Language changed — reload translations
        if (oldLang !== _language) {
          loadI18n(_language).then(function () {
            for (var i = 0; i < _languageCallbacks.length; i++) {
              try { _languageCallbacks[i](_language); } catch (e) { console.error(e); }
            }
          });
        }
      }
    }

    if (data.type === 'langbot:api:response') {
      var requestId = data.requestId;
      if (_pendingRequests[requestId]) {
        if (data.error) {
          _pendingRequests[requestId].reject(new Error(data.error));
        } else {
          _pendingRequests[requestId].resolve(data.data);
        }
        delete _pendingRequests[requestId];
      }
    }
  });

  // Public API
  window.langbot = {
    /** Current theme: 'light' or 'dark' */
    get theme() { return _theme; },

    /** Current language: e.g. 'zh-Hans', 'en-US' */
    get language() { return _language; },

    /** Whether the SDK has received initial context and i18n is loaded */
    get ready() { return _ready && _i18nLoaded; },

    /**
     * Register a callback for when context is first received.
     * If already ready, fires immediately. If context received but i18n
     * still loading, waits for i18n to complete.
     * @param {function({theme: string, language: string}): void} callback
     */
    onReady: function (callback) {
      if (_ready && _i18nLoaded) {
        try { callback({ theme: _theme, language: _language }); } catch (e) { console.error(e); }
      } else if (_i18nPromise) {
        _i18nPromise.then(function () {
          try { callback({ theme: _theme, language: _language }); } catch (e) { console.error(e); }
        });
      } else {
        _readyCallbacks.push(callback);
      }
    },

    /**
     * Register a callback for theme changes.
     * @param {function(string): void} callback
     */
    onThemeChange: function (callback) {
      _themeCallbacks.push(callback);
    },

    /**
     * Register a callback for language changes (after initial load).
     * Translations are already reloaded when this fires.
     * @param {function(string): void} callback
     */
    onLanguageChange: function (callback) {
      _languageCallbacks.push(callback);
    },

    /**
     * Get a translated string by key.
     * Falls back to the provided fallback or the key itself.
     * @param {string} key - The translation key
     * @param {string} [fallback] - Fallback if key not found
     * @returns {string} Translated string
     */
    t: function (key, fallback) {
      return _translations[key] != null ? _translations[key] : (fallback || key);
    },

    /**
     * Manually re-apply translations to all data-i18n elements.
     * Useful after dynamically adding new elements to the DOM.
     */
    applyI18n: function () {
      applyTranslations();
    },

    /**
     * Call the plugin's handle_page_api method.
     * @param {string} endpoint - The API endpoint
     * @param {*} [body] - Request body
     * @param {string} [method='POST'] - HTTP method
     * @returns {Promise<*>} Response data
     */
    api: function (endpoint, body, method) {
      return new Promise(function (resolve, reject) {
        var requestId = 'req_' + (++_requestIdCounter) + '_' + Date.now();
        _pendingRequests[requestId] = { resolve: resolve, reject: reject };

        window.parent.postMessage({
          type: 'langbot:api',
          requestId: requestId,
          endpoint: endpoint,
          method: method || 'POST',
          body: body,
        }, '*');

        // Timeout after 30s
        setTimeout(function () {
          if (_pendingRequests[requestId]) {
            _pendingRequests[requestId].reject(new Error('Request timeout'));
            delete _pendingRequests[requestId];
          }
        }, 30000);
      });
    },
  };
})();
