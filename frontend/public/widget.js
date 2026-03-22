/**
 * LiveAvatar Widget — Bubble + Modal
 *
 * Drop-in script for customer websites. Creates a floating chat button
 * that opens a modal with the avatar player (via iframe to /embed/:slug).
 *
 * Usage:
 *   LiveAvatarWidget.init({
 *     tenantSlug: 'buettelborn',
 *     position: 'bottom-right',   // or 'bottom-left'
 *     primaryColor: '#2563eb'
 *   });
 */
(function () {
  'use strict';

  // Determine origin from the script src so it works on any customer domain
  var scripts = document.getElementsByTagName('script');
  var currentScript = scripts[scripts.length - 1];
  var scriptSrc = currentScript && currentScript.src ? currentScript.src : '';
  var defaultOrigin = scriptSrc ? scriptSrc.replace(/\/widget\.js.*$/, '') : '';

  window.LiveAvatarWidget = {
    init: function (opts) {
      opts = opts || {};
      var tenantSlug = opts.tenantSlug || '';
      var position = opts.position || 'bottom-right';
      var primaryColor = opts.primaryColor || '#2563eb';
      var origin = opts.serverUrl || defaultOrigin || 'https://liveavatar.klink-io.cloud';

      if (!tenantSlug) {
        console.error('[LiveAvatar Widget] tenantSlug is required');
        return;
      }

      var isRight = position.indexOf('right') !== -1;
      var isOpen = false;

      // -------- Styles --------
      var style = document.createElement('style');
      style.textContent = [
        '.la-widget-bubble {',
        '  position: fixed;',
        '  ' + (isRight ? 'right: 24px;' : 'left: 24px;'),
        '  bottom: 24px;',
        '  width: 60px;',
        '  height: 60px;',
        '  border-radius: 50%;',
        '  background: ' + primaryColor + ';',
        '  border: none;',
        '  cursor: pointer;',
        '  display: flex;',
        '  align-items: center;',
        '  justify-content: center;',
        '  box-shadow: 0 4px 20px rgba(0,0,0,0.2);',
        '  z-index: 2147483646;',
        '  transition: transform 0.2s ease, opacity 0.2s ease;',
        '}',
        '.la-widget-bubble:hover { transform: scale(1.1); }',
        '.la-widget-bubble svg { width: 28px; height: 28px; }',
        '',
        '.la-widget-modal {',
        '  position: fixed;',
        '  ' + (isRight ? 'right: 24px;' : 'left: 24px;'),
        '  bottom: 24px;',
        '  width: 400px;',
        '  height: 600px;',
        '  max-height: calc(100vh - 48px);',
        '  max-width: calc(100vw - 48px);',
        '  border: none;',
        '  border-radius: 16px;',
        '  overflow: hidden;',
        '  box-shadow: 0 25px 60px rgba(0,0,0,0.3);',
        '  z-index: 2147483647;',
        '  display: none;',
        '  flex-direction: column;',
        '  background: #fff;',
        '  animation: laWidgetSlideUp 0.3s ease;',
        '}',
        '.la-widget-modal.la-open { display: flex; }',
        '',
        '@keyframes laWidgetSlideUp {',
        '  from { opacity: 0; transform: translateY(20px); }',
        '  to { opacity: 1; transform: translateY(0); }',
        '}',
        '',
        '.la-widget-header {',
        '  display: flex;',
        '  align-items: center;',
        '  justify-content: space-between;',
        '  padding: 10px 14px;',
        '  background: ' + primaryColor + ';',
        '  color: #fff;',
        '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        '  font-size: 14px;',
        '  font-weight: 600;',
        '}',
        '.la-widget-header-btns { display: flex; gap: 4px; }',
        '.la-widget-header-btns button {',
        '  background: transparent;',
        '  border: none;',
        '  color: #fff;',
        '  cursor: pointer;',
        '  padding: 4px;',
        '  border-radius: 4px;',
        '  display: flex;',
        '  align-items: center;',
        '  justify-content: center;',
        '}',
        '.la-widget-header-btns button:hover { background: rgba(255,255,255,0.2); }',
        '.la-widget-header-btns svg { width: 16px; height: 16px; }',
        '',
        '.la-widget-iframe {',
        '  flex: 1;',
        '  border: none;',
        '  width: 100%;',
        '  height: 100%;',
        '}',
        '',
        '@media (max-width: 480px) {',
        '  .la-widget-modal {',
        '    width: 100vw;',
        '    height: 100vh;',
        '    max-width: 100vw;',
        '    max-height: 100vh;',
        '    bottom: 0;',
        '    ' + (isRight ? 'right: 0;' : 'left: 0;'),
        '    border-radius: 0;',
        '  }',
        '}',
      ].join('\n');
      document.head.appendChild(style);

      // -------- Bubble Button --------
      var bubble = document.createElement('button');
      bubble.className = 'la-widget-bubble';
      bubble.setAttribute('aria-label', 'Avatar starten');
      bubble.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
        '</svg>';

      // -------- Modal --------
      var modal = document.createElement('div');
      modal.className = 'la-widget-modal';

      // Header
      var header = document.createElement('div');
      header.className = 'la-widget-header';

      var title = document.createElement('span');
      title.textContent = 'Avatar Assistent';

      var headerBtns = document.createElement('div');
      headerBtns.className = 'la-widget-header-btns';

      var closeBtn = document.createElement('button');
      closeBtn.setAttribute('aria-label', 'Schließen');
      closeBtn.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>' +
        '</svg>';

      headerBtns.appendChild(closeBtn);
      header.appendChild(title);
      header.appendChild(headerBtns);
      modal.appendChild(header);

      // iFrame (embed page)
      var iframe = document.createElement('iframe');
      iframe.className = 'la-widget-iframe';
      iframe.setAttribute('allow', 'microphone; camera; autoplay');
      iframe.setAttribute('title', 'LiveAvatar Widget');
      // Don't load yet — load on open
      modal.appendChild(iframe);

      var embedUrl = origin + '/embed/' + tenantSlug + '?chat=1';

      // -------- Toggle logic --------
      function openWidget() {
        isOpen = true;
        // Load iframe on first open
        if (!iframe.src) {
          iframe.src = embedUrl;
        }
        modal.classList.add('la-open');
        bubble.style.display = 'none';
      }

      function closeWidget() {
        isOpen = false;
        modal.classList.remove('la-open');
        bubble.style.display = 'flex';
      }

      bubble.addEventListener('click', openWidget);
      closeBtn.addEventListener('click', closeWidget);

      // Listen for close messages from the iframe
      window.addEventListener('message', function (event) {
        if (event.data === 'liveavatar-close') {
          closeWidget();
        }
      });

      // -------- Append to DOM --------
      document.body.appendChild(bubble);
      document.body.appendChild(modal);

      // Try to fetch tenant name for the header
      try {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', origin + '/api/v1/tenants/slug/' + tenantSlug, true);
        xhr.onload = function () {
          if (xhr.status === 200) {
            var data = JSON.parse(xhr.responseText);
            if (data.name) title.textContent = data.name;
          }
        };
        xhr.send();
      } catch (e) {
        // Silently ignore — fallback title is fine
      }
    },
  };
})();
