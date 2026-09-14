<div class="kiosco-rejilla">
  <div class="kiosco-actual">
    <p class="kiosco-etiqueta">Atendiendo</p>
    <p class="kiosco-folio" id="folio"><?= $estado['actual'] ? (int) $estado['actual']['folio'] : '—' ?></p>
    <p class="kiosco-nombre" id="nombre">
      <?= $estado['actual']
          ? u_escapar($estado['actual']['nombre_publico'] ?: u_nombre_corto($estado['actual']['nombre']))
          : ($estado['abierta'] ? 'En espera' : u_escapar($estado['motivo_cierre'])) ?>
    </p>
    <p class="kiosco-leyenda <?= $estado['atencion'] ?>" id="leyenda">
      <?= u_escapar(leyenda_atencion($estado)) ?>
    </p>
  </div>

  <div class="kiosco-lado">
    <p class="kiosco-etiqueta">Siguen</p>
    <ul class="kiosco-lista" id="siguientes">
      <?php foreach (array_slice($estado['espera'], 0, 5) as $turno): ?>
      <li><span class="folio-chico"><?= (int) $turno['folio'] ?></span>
        <span><?= u_escapar($turno['nombre_publico'] ?: u_nombre_corto($turno['nombre'])) ?></span>
        <span class="hora"><?= $turno['estimado'] ? u_hora($turno['estimado']) : '—' ?></span></li>
      <?php endforeach; ?>
    </ul>

    <div class="kiosco-qr">
      <div id="qr"></div>
      <p>Escanea para tomar turno o agendar</p>
      <p class="kiosco-url"><?= u_escapar(preg_replace('#^https?://#', '', url_absoluta($dep['clave']))) ?></p>
    </div>
    <p class="kiosco-reloj" id="reloj"><?= u_hora($estado['ahora']) ?></p>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
const destino = <?= json_encode(url_absoluta($dep['clave'])) ?>;
if (window.QRCode) {
  new QRCode(document.getElementById('qr'), {text: destino, width: 220, height: 220,
    colorDark: '#10233a', colorLight: '#ffffff'});
}
async function refrescar() {
  try {
    const datos = await (await fetch('<?= ruta($dep['clave'] . '/estado.json') ?>', {cache: 'no-store'})).json();
    document.getElementById('folio').textContent = datos.actual ? datos.actual.folio : '—';
    document.getElementById('nombre').textContent = datos.actual ? datos.actual.nombre
      : (datos.abierta ? 'En espera' : datos.mensaje);
    document.getElementById('reloj').textContent = datos.ahora;
    const leyenda = document.getElementById('leyenda');
    leyenda.textContent = datos.leyenda;
    leyenda.className = 'kiosco-leyenda ' + datos.atencion;
    document.getElementById('siguientes').innerHTML = datos.siguientes.map(t =>
      `<li><span class="folio-chico">${t.folio}</span><span>${t.nombre}</span>` +
      `<span class="hora">${t.hora || '—'}</span></li>`).join('');
  } catch (e) { /* si el servidor no responde, la pantalla se queda como estaba */ }
}
setInterval(refrescar, 5000);
</script>
