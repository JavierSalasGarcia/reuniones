<section class="tarjeta">
  <h1><?= u_escapar($dep['nombre']) ?></h1>
  <p class="meta"><?= u_escapar($dep['titular']) ?></p>

  <p class="leyenda <?= $estado['atencion'] ?>"><?= u_escapar(leyenda_atencion($estado)) ?></p>

  <?php if ($estado['abierta']): ?>
    <p class="estado bien">Fila abierta.
      <?php if ($estado['tope']): ?>Puedes formarte hasta las <?= u_hora($estado['tope']) ?>.<?php endif; ?>
      <?php if ($estado['proximo_hueco']): ?>
      Si tomas turno ahora, te tocaría alrededor de las
      <strong><?= u_hora($estado['proximo_hueco']) ?></strong>.
      <?php endif; ?>
    </p>
  <?php else: ?>
    <p class="estado aviso"><?= u_escapar($estado['motivo_cierre']) ?>
      Puedes solicitar una reunión para otro día.</p>
  <?php endif; ?>

  <?php if ($error): ?><p class="error"><?= u_escapar($error) ?></p><?php endif; ?>

  <form method="post" action="<?= ruta($dep['clave'] . '/confirmar') ?>" enctype="multipart/form-data"
        class="formulario" id="forma">
    <?= campo_csrf() ?>
    <input type="hidden" name="tipo" id="tipo" value="<?= $estado['abierta'] ? 'turno' : 'cita' ?>">

    <label>Nombre completo
      <input name="nombre" required maxlength="120" value="<?= u_escapar($datos['nombre'] ?? '') ?>">
    </label>
    <label>Correo institucional
      <input name="email" type="email" required placeholder="usuario@<?= u_escapar($dep['dominio_correo']) ?>"
             value="<?= u_escapar($datos['email'] ?? '') ?>">
    </label>
    <label>¿De qué se trata? (una línea)
      <input name="asunto" required maxlength="200" value="<?= u_escapar($datos['asunto'] ?? '') ?>">
    </label>

    <fieldset class="tiempo">
      <legend>¿Cuánto tiempo necesitas?</legend>
      <label class="opcion"><input type="radio" name="duracion" value="5"
             <?= $estado['abierta'] ? 'checked' : 'disabled' ?>>
        <span><strong>5 minutos</strong><br>Una firma, una duda rápida</span></label>
      <label class="opcion"><input type="radio" name="duracion" value="<?= (int) $dep['duracion_max'] ?>"
             <?= $estado['abierta'] ? '' : 'disabled' ?>>
        <span><strong><?= (int) $dep['duracion_max'] ?> minutos</strong><br>Un asunto que requiere explicarse</span></label>
      <label class="opcion"><input type="radio" name="duracion" value="cita"
             <?= $estado['abierta'] ? '' : 'checked' ?>>
        <span><strong>Más de <?= (int) $dep['duracion_max'] ?> minutos</strong><br>Se agenda como reunión</span></label>
    </fieldset>

    <input type="hidden" name="minutos" id="minutos" value="5">

    <div id="bloque-cita" hidden>
      <label>Duración de la reunión
        <select name="minutos_cita" id="minutos_cita">
          <?php foreach ($minutos_cita as $opcion): ?>
          <option value="<?= $opcion ?>"><?= $opcion ?> minutos</option>
          <?php endforeach; ?>
        </select>
      </label>
      <label>Día y hora
        <select name="hora" id="hora">
          <?php foreach ($huecos as $dia): ?>
          <optgroup label="<?= u_escapar(u_fecha_larga($dia['dia']->setTime(0, 0))) ?>">
            <?php foreach ($dia['opciones'] as $opcion): ?>
            <option value="<?= $opcion->format('Y-m-d H:i') ?>"><?= u_hora($opcion) ?></option>
            <?php endforeach; ?>
          </optgroup>
          <?php endforeach; ?>
        </select>
      </label>
      <p class="meta">Al cambiar la duración se recalculan las horas libres.</p>
      <label>Cuéntame el caso
        <textarea name="descripcion" rows="5" maxlength="4000"
                  placeholder="Antecedentes, qué has intentado, qué necesitas"></textarea>
      </label>
      <label>Archivos (opcional, hasta 5)
        <input type="file" name="archivos[]" multiple
               accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.txt">
      </label>
    </div>

    <button class="grande">Continuar</button>
    <p class="meta">Te enviaremos un código a tu correo institucional para confirmar.
      Recuerda que si no estás presente cuando te toque, se atenderá a quien siga.</p>
  </form>

  <p><a href="<?= ruta($dep['clave'] . '/fila') ?>">Ver cómo va la fila</a></p>
</section>

<script>
const forma = document.getElementById('forma');
const bloque = document.getElementById('bloque-cita');
const tipo = document.getElementById('tipo');
const minutos = document.getElementById('minutos');
const duraciones = forma.querySelectorAll('input[name="duracion"]');

function actualizar() {
  const elegido = forma.querySelector('input[name="duracion"]:checked');
  const esCita = !elegido || elegido.value === 'cita';
  bloque.hidden = !esCita;
  tipo.value = esCita ? 'cita' : 'turno';
  minutos.value = esCita ? '' : elegido.value;
  forma.querySelector('#hora').required = esCita;
}
duraciones.forEach(d => d.addEventListener('change', actualizar));
document.getElementById('minutos_cita').addEventListener('change', async (evento) => {
  const respuesta = await fetch(location.pathname + '?huecos=' + evento.target.value, {headers: {'Accept': 'application/json'}});
  if (!respuesta.ok) return;
  const datos = await respuesta.json();
  const hora = document.getElementById('hora');
  hora.innerHTML = datos.dias.map(d =>
    `<optgroup label="${d.etiqueta}">` +
    d.opciones.map(o => `<option value="${o.valor}">${o.hora}</option>`).join('') +
    '</optgroup>').join('');
});
actualizar();
</script>
