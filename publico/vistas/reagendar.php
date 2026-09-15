<section class="tarjeta">
  <h1>Elige otra fecha</h1>
  <p class="meta"><?= u_escapar($dep['nombre']) ?> · <?= u_escapar($dep['titular']) ?></p>

  <p>Tu solicitud
    <?= $cita['estado'] === 'cancelada' ? 'fue cancelada' : 'no pudo confirmarse' ?>
    <?php if ($cita['motivo']): ?>: <?= u_escapar($cita['motivo']) ?><?php endif; ?>.
    Aquí puedes proponer otra hora; tus datos y tus archivos se conservan.</p>

  <p class="meta">
    <?= u_escapar($cita['nombre']) ?> · <?= u_escapar($cita['email']) ?><br>
    <?= u_escapar($cita['asunto']) ?> · <?= (int) $cita['minutos'] ?> minutos
    <?php if ($adjuntos): ?><br><?= count($adjuntos) ?> archivo(s) ya enviados<?php endif; ?>
  </p>

  <?php if ($error): ?><p class="error"><?= u_escapar($error) ?></p><?php endif; ?>

  <?php if ($huecos): ?>
  <form method="post" class="formulario">
    <?= campo_csrf() ?>
    <label>Día y hora
      <select name="hora" required>
        <?php foreach ($huecos as $dia): ?>
        <optgroup label="<?= u_escapar(u_fecha_larga($dia['dia']->setTime(0, 0))) ?>">
          <?php foreach ($dia['opciones'] as $opcion): ?>
          <option value="<?= $opcion->format('Y-m-d H:i') ?>"><?= u_hora($opcion) ?></option>
          <?php endforeach; ?>
        </optgroup>
        <?php endforeach; ?>
      </select>
    </label>
    <button class="grande">Enviar la nueva solicitud</button>
    <p class="meta">Queda pendiente de confirmación, igual que la primera vez.</p>
  </form>
  <?php else: ?>
  <p class="estado aviso">No hay horas libres por ahora. Inténtalo más tarde.</p>
  <?php endif; ?>
</section>
