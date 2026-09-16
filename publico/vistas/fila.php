<section class="tarjeta">
  <h1>La fila de hoy</h1>
  <p class="meta"><?= u_escapar($dep['nombre']) ?> · actualizado a las <?= u_hora($estado['ahora']) ?></p>
  <p class="leyenda <?= $estado['atencion'] ?>"><?= u_escapar(leyenda_atencion($estado)) ?></p>

  <?php if ($estado['actual']): ?>
  <div class="atendiendo">
    <span class="etiqueta">Atendiendo</span>
    <strong class="folio"><?= (int) $estado['actual']['folio'] ?></strong>
    <?php if (muestra_nombres($dep)): ?>
    <span><?= u_escapar(etiqueta_publica($dep, $estado['actual'])) ?></span>
    <?php endif; ?>
  </div>
  <?php else: ?>
  <p class="estado <?= $estado['abierta'] ? 'bien' : 'aviso' ?>">
    <?= $estado['abierta'] ? 'Nadie está siendo atendido en este momento.' : u_escapar($estado['motivo_cierre']) ?>
  </p>
  <?php endif; ?>

  <?php if ($estado['espera']): ?>
  <table class="tabla">
    <thead><tr><th>Turno</th><?php if (muestra_nombres($dep)): ?><th>Persona</th><?php endif; ?>
      <th>Hora aproximada</th></tr></thead>
    <tbody>
      <?php foreach ($estado['espera'] as $turno): ?>
      <tr>
        <td class="folio-chico"><?= (int) $turno['folio'] ?></td>
        <?php if (muestra_nombres($dep)): ?>
        <td><?= u_escapar(etiqueta_publica($dep, $turno)) ?></td>
        <?php endif; ?>
        <td><?= $turno['estimado'] ? u_hora($turno['estimado']) : 'sin hora hoy' ?></td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>
  <?php else: ?>
  <p class="meta">No hay nadie esperando.</p>
  <?php endif; ?>

  <?php if ($estado['bloqueos']): ?>
  <h2>Reuniones agendadas hoy</h2>
  <ul class="lista chica">
    <?php foreach ($estado['bloqueos'] as $bloqueo): ?>
    <li><?= u_hora($bloqueo['inicio']) ?> a <?= u_hora($bloqueo['fin']) ?>
      <span class="meta"><?= u_escapar($bloqueo['motivo']) ?></span></li>
    <?php endforeach; ?>
  </ul>
  <p class="meta">Los turnos que caen en esos horarios se recorren automáticamente.</p>
  <?php endif; ?>

  <p><a class="boton" href="<?= ruta($dep['clave']) ?>">Tomar turno</a></p>
</section>
<script>setTimeout(() => location.reload(), 30000);</script>
