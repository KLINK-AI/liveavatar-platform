/**
 * LiveAvatar Widget — Bubble + Modal (Landscape)
 *
 * Drop-in script for customer websites. Creates a floating avatar preview
 * button that opens a landscape modal with the avatar player (via iframe).
 *
 * Usage:
 *   LiveAvatarWidget.init({
 *     tenantSlug: 'buettelborn',
 *     position: 'bottom-right',   // or 'bottom-left'
 *     primaryColor: '#2563eb',
 *     bubbleText: 'Chat starten'  // optional
 *   });
 */
(function () {
  'use strict';

  // Determine origin from the script src
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
      var bubbleText = opts.bubbleText || 'Avatar starten';
      var origin = opts.serverUrl || defaultOrigin || 'https://liveavatar.klink-io.cloud';

      if (!tenantSlug) {
        console.error('[LiveAvatar Widget] tenantSlug is required');
        return;
      }

      var isRight = position.indexOf('right') !== -1;
      var isOpen = false;
      var sessionActive = false;
      var tenantName = '';
      var previewImageUrl = '';

      // -------- Styles --------
      var style = document.createElement('style');
      style.textContent = [
        /* --- Bubble: avatar image + text label --- */
        '.la-widget-bubble {',
        '  position: fixed;',
        '  ' + (isRight ? 'right: 20px;' : 'left: 20px;'),
        '  bottom: 20px;',
        '  display: flex;',
        '  align-items: center;',
        '  gap: 0;',
        '  cursor: pointer;',
        '  z-index: 2147483646;',
        '  transition: transform 0.2s ease;',
        '  border: none;',
        '  background: none;',
        '  padding: 0;',
        '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        '}',
        '.la-widget-bubble:hover { transform: scale(1.05); }',
        '',
        '.la-bubble-avatar {',
        '  width: 64px;',
        '  height: 64px;',
        '  border-radius: 50%;',
        '  object-fit: cover;',
        '  border: 3px solid ' + primaryColor + ';',
        '  box-shadow: 0 4px 16px rgba(0,0,0,0.2);',
        '  flex-shrink: 0;',
        '}',
        '.la-bubble-avatar-fallback {',
        '  width: 64px;',
        '  height: 64px;',
        '  border-radius: 50%;',
        '  background: ' + primaryColor + ';',
        '  display: flex;',
        '  align-items: center;',
        '  justify-content: center;',
        '  border: 3px solid ' + primaryColor + ';',
        '  box-shadow: 0 4px 16px rgba(0,0,0,0.2);',
        '  flex-shrink: 0;',
        '}',
        '.la-bubble-avatar-fallback svg { width: 28px; height: 28px; }',
        '',
        '.la-bubble-label {',
        '  background: ' + primaryColor + ';',
        '  color: #fff;',
        '  padding: 6px 14px 6px 10px;',
        '  border-radius: 0 20px 20px 0;',
        '  font-size: 13px;',
        '  font-weight: 600;',
        '  white-space: nowrap;',
        '  box-shadow: 0 2px 8px rgba(0,0,0,0.15);',
        '  margin-left: -6px;',
        '  line-height: 1.3;',
        '}',
        '',
        /* --- Modal: landscape layout --- */
        '.la-widget-modal {',
        '  position: fixed;',
        '  ' + (isRight ? 'right: 20px;' : 'left: 20px;'),
        '  bottom: 20px;',
        '  width: 720px;',
        '  height: 460px;',
        '  max-width: calc(100vw - 40px);',
        '  max-height: calc(100vh - 40px);',
        '  border: none;',
        '  border-radius: 16px;',
        '  overflow: hidden;',
        '  box-shadow: 0 25px 60px rgba(0,0,0,0.3);',
        '  z-index: 2147483647;',
        '  display: none;',
        '  flex-direction: column;',
        '  background: #000;',
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
        '  padding: 8px 14px;',
        '  background: ' + primaryColor + ';',
        '  color: #fff;',
        '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        '  font-size: 14px;',
        '  font-weight: 600;',
        '  flex-shrink: 0;',
        '}',
        '.la-widget-header-btns { display: flex; gap: 2px; align-items: center; }',
        '.la-widget-header-btns button {',
        '  background: transparent;',
        '  border: none;',
        '  color: #fff;',
        '  cursor: pointer;',
        '  padding: 5px 8px;',
        '  border-radius: 6px;',
        '  display: flex;',
        '  align-items: center;',
        '  justify-content: center;',
        '  font-family: inherit;',
        '  font-size: 12px;',
        '  gap: 4px;',
        '}',
        '.la-widget-header-btns button:hover { background: rgba(255,255,255,0.2); }',
        '.la-widget-header-btns svg { width: 16px; height: 16px; }',
        '',
        '.la-end-session-btn {',
        '  background: rgba(255,255,255,0.15) !important;',
        '  border: 1px solid rgba(255,255,255,0.3) !important;',
        '  padding: 4px 10px !important;',
        '  border-radius: 6px !important;',
        '  font-size: 11px !important;',
        '  margin-right: 4px;',
        '}',
        '.la-end-session-btn:hover { background: rgba(255,60,60,0.6) !important; }',
        '',
        '.la-widget-iframe {',
        '  flex: 1;',
        '  border: none;',
        '  width: 100%;',
        '  height: 100%;',
        '}',
        '',
        /* --- Mobile: full screen --- */
        '@media (max-width: 760px) {',
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

      // -------- Bubble Button (avatar image + label) --------
      var bubble = document.createElement('button');
      bubble.className = 'la-widget-bubble';
      bubble.setAttribute('aria-label', bubbleText);

      // Avatar image — loaded directly as <img> from the backend image endpoint
      // (img tags don't need CORS, so this works from any customer domain)
      var avatarImg = document.createElement('img');
      avatarImg.className = 'la-bubble-avatar';
      avatarImg.src = origin + '/api/v1/tenants/by-slug/' + tenantSlug + '/avatar.jpg';
      avatarImg.alt = 'Avatar';
      avatarImg.onerror = function () {
        // Fallback to chat icon if image fails
        var fallback = document.createElement('div');
        fallback.className = 'la-bubble-avatar-fallback';
        fallback.innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
          '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
          '</svg>';
        bubble.replaceChild(fallback, avatarImg);
      };

      var label = document.createElement('span');
      label.className = 'la-bubble-label';
      label.textContent = bubbleText;

      bubble.appendChild(avatarImg);
      bubble.appendChild(label);

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

      // "Session beenden" button (hidden until session is active)
      var endBtn = document.createElement('button');
      endBtn.className = 'la-end-session-btn';
      endBtn.setAttribute('aria-label', 'Session beenden');
      endBtn.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;">' +
        '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>' +
        '</svg>' +
        '<span>Beenden</span>';
      endBtn.style.display = 'none';

      // Close (X) button
      var closeBtn = document.createElement('button');
      closeBtn.setAttribute('aria-label', 'Schließen');
      closeBtn.innerHTML =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>' +
        '</svg>';

      headerBtns.appendChild(endBtn);
      headerBtns.appendChild(closeBtn);
      header.appendChild(title);
      header.appendChild(headerBtns);
      modal.appendChild(header);

      // iFrame (embed page — NO ?chat=1, chat is hidden by default)
      var iframe = document.createElement('iframe');
      iframe.className = 'la-widget-iframe';
      iframe.setAttribute('allow', 'microphone; camera; autoplay');
      iframe.setAttribute('title', 'LiveAvatar Widget');
      modal.appendChild(iframe);

      var embedUrl = origin + '/embed/' + tenantSlug;

      // -------- Toggle logic --------
      function openWidget() {
        isOpen = true;
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

      function endSession() {
        // Send message to iframe to stop session
        if (iframe.contentWindow) {
          iframe.contentWindow.postMessage('liveavatar-end-session', '*');
        }
        // Reset iframe to reload fresh
        var currentSrc = iframe.src;
        iframe.src = '';
        iframe.src = currentSrc;
        sessionActive = false;
        endBtn.style.display = 'none';
      }

      bubble.addEventListener('click', openWidget);
      closeBtn.addEventListener('click', closeWidget);
      endBtn.addEventListener('click', endSession);

      // Listen for messages from the iframe
      window.addEventListener('message', function (event) {
        if (event.data === 'liveavatar-close') {
          closeWidget();
        }
        if (event.data === 'liveavatar-session-started') {
          sessionActive = true;
          endBtn.style.display = 'flex';
        }
        if (event.data === 'liveavatar-session-ended') {
          sessionActive = false;
          endBtn.style.display = 'none';
        }
      });

      // -------- Append to DOM --------
      document.body.appendChild(bubble);
      document.body.appendChild(modal);

      // -------- Load tenant name for header --------
      try {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', origin + '/api/v1/tenants/slug/' + tenantSlug, true);
        xhr.onload = function () {
          if (xhr.status === 200) {
            var data = JSON.parse(xhr.responseText);
            if (data.name) {
              tenantName = data.name;
              title.textContent = data.name;
            }
          }
        };
        xhr.send();
      } catch (e) {
        // Silently ignore — fallback appearance is fine
      }
    },
  };
})();
