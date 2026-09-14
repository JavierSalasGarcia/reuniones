<section class="tarjeta">
  <h1><?= u_escapar($titulo_aviso) ?></h1>
  <p><?= u_escapar($texto) ?></p>
  <?php if ($dep): ?>
  <p><a class="boton" href="<?= ruta($dep['clave']) ?>">Volver</a></p>
  <?php endif; ?>
</section>
