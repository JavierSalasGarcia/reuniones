<section class="tarjeta angosta">
  <p class="meta"><?= u_escapar($dep['nombre']) ?></p>
  <h1>Solicitud de reunión</h1>

  <?php if ($cita['estado'] === 'solicitada'): ?>
    <p class="estado aviso">En espera de confirmación.</p>
    <p>Propusiste el <strong><?= u_escapar(u_fecha_larga(a_momento($cita['propuesta']))) ?></strong>.</p>
  <?php elseif ($cita['estado'] === 'aprobada'): ?>
    <p class="estado bien">Confirmada.</p>
    <p><strong><?= u_escapar(u_fecha_larga(a_momento($cita['confirmada'] ?: $cita['propuesta']))) ?></strong>,
       <?= (int) $cita['minutos'] ?> minutos.</p>
  <?php elseif ($cita['estado'] === 'rechazada'): ?>
    <p class="estado aviso">No se confirmó en esa fecha.</p>
    <?php if ($cita['motivo']): ?><p><?= u_escapar($cita['motivo']) ?></p><?php endif; ?>
    <p><a class="boton" href="<?= ruta($dep['clave']) ?>">Proponer otra fecha</a></p>
  <?php else: ?>
    <p class="estado aviso">Cancelada.</p>
  <?php endif; ?>

  <p class="meta">Asunto: <?= u_escapar($cita['asunto']) ?></p>
  <?php if ($adjuntos): ?>
  <p class="meta">Archivos enviados: <?= count($adjuntos) ?></p>
  <?php endif; ?>

  <?php if (in_array($cita['estado'], ['solicitada', 'aprobada'], true)): ?>
  <form method="post" class="formulario">
    <?= campo_csrf() ?>
    <input type="hidden" name="accion" value="cancelar">
    <button class="secundario">Cancelar la solicitud</button>
  </form>
  <?php endif; ?>
</section>
