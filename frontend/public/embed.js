/**
 * LiveAvatar Embed Script
 *
 * Include this on any website to add the avatar widget:
 *
 * <script
 *   src="https://your-server.com/embed.js"
 *   data-api-key="your-tenant-api-key"
 *   data-tenant="your-tenant-slug"
 *   data-position="bottom-right"
 *   data-primary-color="#2563eb"
 * ></script>
 */
(function() {
  'use strict';

  // Get config from script tag
  const script = document.currentScript;
  const config = {
    apiKey: script.getAttribute('data-api-key') || '',
    tenant: script.getAttribute('data-tenant') || '',
    position: script.getAttribute('data-position') || 'bottom-right',
    primaryColor: script.getAttribute('data-primary-color') || '#2563eb',
    serverUrl: script.getAttribute('data-server') || script.src.replace('/embed.js', ''),
  };

  if (!config.apiKey || !config.tenant) {
    console.error('[LiveAvatar] Missing data-api-key or data-tenant attribute');
    return;
  }

  // Create iframe
  const iframe = document.createElement('iframe');
  iframe.src = `${config.serverUrl}/avatar/${config.tenant}?embed=true&apiKey=${config.apiKey}`;
  iframe.style.cssText = `
    position: fixed;
    ${config.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
    bottom: 20px;
    width: 420px;
    height: 700px;
    border: none;
    border-radius: 16px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    z-index: 99999;
    transition: all 0.3s ease;
  `;
  iframe.setAttribute('allow', 'microphone; camera');

  // Initially hidden — show via floating button
  iframe.style.display = 'none';

  // Create floating button
  const button = document.createElement('button');
  button.innerHTML = `
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  `;
  button.style.cssText = `
    position: fixed;
    ${config.position.includes('right') ? 'right: 24px;' : 'left: 24px;'}
    bottom: 24px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: ${config.primaryColor};
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 99999;
    transition: transform 0.2s ease;
  `;
  button.onmouseenter = function() { this.style.transform = 'scale(1.1)'; };
  button.onmouseleave = function() { this.style.transform = 'scale(1)'; };

  let isOpen = false;
  button.onclick = function() {
    isOpen = !isOpen;
    iframe.style.display = isOpen ? 'block' : 'none';
    button.style.display = isOpen ? 'none' : 'flex';
  };

  // Listen for close messages from iframe
  window.addEventListener('message', function(event) {
    if (event.data === 'liveavatar-close') {
      isOpen = false;
      iframe.style.display = 'none';
      button.style.display = 'flex';
    }
  });

  document.body.appendChild(iframe);
  document.body.appendChild(button);
})();
