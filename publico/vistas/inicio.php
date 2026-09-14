<section class="tarjeta">
  <h1>Citas y turnos</h1>
  <?php if ($lista): ?>
  <p>Elige la oficina que buscas.</p>
  <ul class="lista">
    <?php foreach ($lista as $fila): ?>
    <li><a href="<?= ruta($fila['clave']) ?>"><strong><?= u_escapar($fila['nombre']) ?></strong></a>
      <span class="meta"><?= u_escapar($fila['titular']) ?></span></li>
    <?php endforeach; ?>
  </ul>
  <?php else: ?>
  <p>Todavía no hay oficinas dadas de alta.</p>
  <?php endif; ?>
</section>
