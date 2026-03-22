/**
 * Embed Code Generator
 *
 * Shows copyable embed codes for a tenant:
 * 1. iFrame embed — simple HTML iframe tag
 * 2. Widget (Bubble+Modal) — JavaScript snippet
 *
 * Used in the Admin Dashboard / Tenant Manager.
 */

import { useState } from 'react'
import { Copy, Check, Code, Monitor, MessageCircle } from 'lucide-react'

interface EmbedCodeGeneratorProps {
  tenantSlug: string
  tenantName: string
  primaryColor?: string
  baseUrl?: string
}

export default function EmbedCodeGenerator({
  tenantSlug,
  tenantName,
  primaryColor = '#2563eb',
  baseUrl,
}: EmbedCodeGeneratorProps) {
  const [activeTab, setActiveTab] = useState<'iframe' | 'widget'>('iframe')
  const [copied, setCopied] = useState(false)
  const [iframeWidth, setIframeWidth] = useState('600')
  const [iframeHeight, setIframeHeight] = useState('450')
  const [autostart, setAutostart] = useState(false)
  const [widgetPosition, setWidgetPosition] = useState<'bottom-right' | 'bottom-left'>('bottom-right')

  // Auto-detect base URL from current location
  const origin = baseUrl || (typeof window !== 'undefined' ? window.location.origin : 'https://liveavatar.klink-io.cloud')

  const iframeParams = new URLSearchParams()
  if (autostart) iframeParams.set('autostart', '1')
  const paramString = iframeParams.toString()
  const embedUrl = `${origin}/embed/${tenantSlug}${paramString ? '?' + paramString : ''}`

  const iframeCode = `<iframe
  src="${embedUrl}"
  width="${iframeWidth}"
  height="${iframeHeight}"
  frameborder="0"
  allow="microphone; camera"
  style="border-radius: 12px; border: 1px solid #e5e7eb;"
  title="${tenantName} Avatar">
</iframe>`

  const widgetCode = `<!-- ${tenantName} Avatar Widget -->
<script>
(function() {
  var d = document, s = d.createElement('script');
  s.src = '${origin}/widget.js';
  s.async = true;
  s.onload = function() {
    LiveAvatarWidget.init({
      tenantSlug: '${tenantSlug}',
      position: '${widgetPosition}',
      primaryColor: '${primaryColor}'
    });
  };
  d.body.appendChild(s);
})();
</script>`

  const currentCode = activeTab === 'iframe' ? iframeCode : widgetCode

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const textarea = document.createElement('textarea')
      textarea.value = currentCode
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('iframe')}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'iframe'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/50'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Monitor className="w-4 h-4" />
          iFrame Embed
        </button>
        <button
          onClick={() => setActiveTab('widget')}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'widget'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/50'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <MessageCircle className="w-4 h-4" />
          Widget (Bubble)
        </button>
      </div>

      <div className="p-4">
        {/* Options */}
        {activeTab === 'iframe' && (
          <div className="flex flex-wrap items-center gap-4 mb-4">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              Breite:
              <input
                type="number"
                value={iframeWidth}
                onChange={(e) => setIframeWidth(e.target.value)}
                className="w-20 px-2 py-1 rounded border border-gray-300 text-sm"
              />
              px
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              H\u00f6he:
              <input
                type="number"
                value={iframeHeight}
                onChange={(e) => setIframeHeight(e.target.value)}
                className="w-20 px-2 py-1 rounded border border-gray-300 text-sm"
              />
              px
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={autostart}
                onChange={(e) => setAutostart(e.target.checked)}
                className="rounded"
              />
              Autostart
            </label>
          </div>
        )}

        {activeTab === 'widget' && (
          <div className="flex items-center gap-4 mb-4">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              Position:
              <select
                value={widgetPosition}
                onChange={(e) => setWidgetPosition(e.target.value as any)}
                className="px-2 py-1 rounded border border-gray-300 text-sm"
              >
                <option value="bottom-right">Unten rechts</option>
                <option value="bottom-left">Unten links</option>
              </select>
            </label>
          </div>
        )}

        {/* Code block */}
        <div className="relative">
          <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto leading-relaxed">
            <code>{currentCode}</code>
          </pre>

          <button
            onClick={handleCopy}
            className={`absolute top-3 right-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              copied
                ? 'bg-green-500 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5" />
                Kopiert!
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Kopieren
              </>
            )}
          </button>
        </div>

        {/* Preview hint */}
        <div className="mt-3 flex items-start gap-2 text-xs text-gray-500">
          <Code className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          {activeTab === 'iframe' ? (
            <span>
              F\u00fcgen Sie diesen Code in den HTML-Quellcode Ihrer Webseite ein, wo der Avatar erscheinen soll.
              Der iFrame passt sich an die angegebene Gr\u00f6\u00dfe an. Vergessen Sie nicht,{' '}
              <code className="bg-gray-100 px-1 rounded">allow="microphone"</code> f\u00fcr die Sprachsteuerung.
            </span>
          ) : (
            <span>
              F\u00fcgen Sie diesen Code vor dem schlie\u00dfenden <code className="bg-gray-100 px-1 rounded">&lt;/body&gt;</code>-Tag ein.
              Es erscheint ein schwebender Button, der das Avatar-Widget \u00f6ffnet.
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
