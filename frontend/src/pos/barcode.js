// Captura de lector de código de barras (modo HID-keyboard).
//
// Heurística: los scanners USB emiten los caracteres muy rápido (<30ms entre teclas)
// y terminan con Enter. Si el usuario tipea manualmente es mucho más lento.
// Ignoramos la captura cuando el foco está en un <input> o <textarea>.

const MAX_GAP_MS = 40
const MIN_LENGTH = 4

export function installBarcodeListener(onScan) {
  let buffer = ''
  let lastT = 0

  function onKey(e) {
    const target = e.target
    if (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      (target && target.isContentEditable)
    ) {
      return // no interferimos con inputs normales
    }

    const now = Date.now()
    if (now - lastT > MAX_GAP_MS) buffer = ''
    lastT = now

    if (e.key === 'Enter') {
      if (buffer.length >= MIN_LENGTH) {
        const code = buffer
        buffer = ''
        onScan(code)
        e.preventDefault()
      }
      return
    }

    if (e.key.length === 1) {
      buffer += e.key
    }
  }

  window.addEventListener('keydown', onKey)
  return () => window.removeEventListener('keydown', onKey)
}
