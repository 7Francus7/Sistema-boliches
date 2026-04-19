// Impresión ESC/POS desde el navegador.
// Usa Web Serial (cable/USB-serial) si está disponible; si no, Web Bluetooth.
// Fallback: impresión del ticket en una ventana HTML (para máquinas sin permisos).
//
// Docs de ESC/POS:
//   ESC @       = init            -> 0x1B 0x40
//   ESC a n     = align (0..2)    -> 0x1B 0x61 n
//   GS ! n      = double size     -> 0x1D 0x21 n
//   LF          = newline         -> 0x0A
//   GS V 66 0   = cut partial      -> 0x1D 0x56 0x42 0x00

const ENC = new TextEncoder()

function cmd(...bytes) {
  return new Uint8Array(bytes)
}
function txt(s) {
  return ENC.encode(s)
}
function concat(...chunks) {
  const len = chunks.reduce((a, c) => a + c.length, 0)
  const out = new Uint8Array(len)
  let o = 0
  for (const c of chunks) {
    out.set(c, o)
    o += c.length
  }
  return out
}

function buildTicket({ venue, event, sale, items }) {
  const init = cmd(0x1b, 0x40)
  const alignCenter = cmd(0x1b, 0x61, 0x01)
  const alignLeft = cmd(0x1b, 0x61, 0x00)
  const bigOn = cmd(0x1d, 0x21, 0x11)
  const bigOff = cmd(0x1d, 0x21, 0x00)
  const cut = cmd(0x0a, 0x0a, 0x0a, 0x1d, 0x56, 0x42, 0x00)

  const header = concat(
    alignCenter,
    bigOn,
    txt(`${venue || 'BOLICHE'}\n`),
    bigOff,
    txt(`${event || ''}\n`),
    txt(`${new Date(sale.created_at).toLocaleString()}\n`),
    txt('--------------------------------\n'),
  )

  const lines = items.map((i) => {
    const name = i.name.slice(0, 18).padEnd(18, ' ')
    const qty = String(i.qty).padStart(2, ' ')
    const subtotal = (i.qty * Number(i.unit_price)).toFixed(0).padStart(8, ' ')
    return txt(`${name} x${qty} ${subtotal}\n`)
  })

  const total = concat(
    txt('--------------------------------\n'),
    alignCenter,
    bigOn,
    txt(`TOTAL $${Number(sale.total).toFixed(0)}\n`),
    bigOff,
    txt(`${sale.payment_method.toUpperCase()}\n`),
    txt(`#${sale.client_uuid.slice(0, 8)}\n`),
  )

  return concat(init, header, alignLeft, ...lines, total, cut)
}

async function printSerial(bytes) {
  // Web Serial requiere permisos explícitos del usuario (se pide una vez).
  const port = await navigator.serial.requestPort()
  await port.open({ baudRate: 9600 })
  const writer = port.writable.getWriter()
  await writer.write(bytes)
  writer.releaseLock()
  await port.close()
}

async function printBluetooth(bytes) {
  const device = await navigator.bluetooth.requestDevice({
    filters: [{ services: ['000018f0-0000-1000-8000-00805f9b34fb'] }],
  })
  const server = await device.gatt.connect()
  const service = await server.getPrimaryService('000018f0-0000-1000-8000-00805f9b34fb')
  const characteristic = await service.getCharacteristic('00002af1-0000-1000-8000-00805f9b34fb')
  // Chunkeamos en 180 bytes (BLE MTU típico).
  const CHUNK = 180
  for (let i = 0; i < bytes.length; i += CHUNK) {
    await characteristic.writeValue(bytes.slice(i, i + CHUNK))
  }
  device.gatt.disconnect()
}

function printHTMLFallback({ venue, event, sale, items }) {
  const w = window.open('', '_blank', 'width=320,height=600')
  if (!w) return
  const rows = items
    .map(
      (i) =>
        `<tr><td>${i.name}</td><td style="text-align:right">x${i.qty}</td><td style="text-align:right">$${(i.qty * i.unit_price).toFixed(0)}</td></tr>`,
    )
    .join('')
  w.document.write(`
    <html><head><title>Ticket</title>
    <style>
      body{font-family:monospace;font-size:14px;width:300px;margin:0;padding:8px;color:#000}
      h1{text-align:center;margin:0}
      table{width:100%;border-collapse:collapse}
      td{padding:2px 0}
      .total{font-size:22px;text-align:center;margin-top:8px;border-top:1px dashed #000;padding-top:6px}
    </style></head><body>
    <h1>${venue || 'BOLICHE'}</h1>
    <div style="text-align:center">${event || ''}</div>
    <div style="text-align:center">${new Date(sale.created_at).toLocaleString()}</div>
    <hr/>
    <table>${rows}</table>
    <div class="total">TOTAL $${Number(sale.total).toFixed(0)}</div>
    <div style="text-align:center">${sale.payment_method.toUpperCase()} · #${sale.client_uuid.slice(0,8)}</div>
    <script>window.print();setTimeout(()=>window.close(),500);</script>
    </body></html>
  `)
  w.document.close()
}

export async function printTicket(payload) {
  const bytes = buildTicket(payload)
  try {
    if ('serial' in navigator) {
      await printSerial(bytes)
      return 'serial'
    }
  } catch (e) {
    console.warn('[escpos] serial failed', e.message)
  }
  try {
    if ('bluetooth' in navigator) {
      await printBluetooth(bytes)
      return 'bluetooth'
    }
  } catch (e) {
    console.warn('[escpos] bluetooth failed', e.message)
  }
  printHTMLFallback(payload)
  return 'html'
}
