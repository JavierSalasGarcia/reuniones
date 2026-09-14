<section class="tarjeta angosta">
  <h1>Confirma tu correo</h1>
  <p>Te enviamos un código de seis dígitos a <strong><?= u_escapar($email) ?></strong>.
     Escríbelo aquí para <?= $tipo === 'cita' ? 'enviar tu solicitud de reunión' : 'apartar tu turno' ?>.</p>
  <?php if ($error): ?><p class="error"><?= u_escapar($error) ?></p><?php endif; ?>
  <form method="post" action="<?= ruta($dep['clave'] . '/codigo') ?>" class="formulario">
    <?= campo_csrf() ?>
    <input type="hidden" name="email" value="<?= u_escapar($email) ?>">
    <input type="hidden" name="tipo" value="<?= u_escapar($tipo) ?>">
    <label>Código
      <input name="codigo" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required autofocus
             class="codigo">
    </label>
    <button class="grande">Confirmar</button>
  </form>
  <p class="meta">Si no llega en un par de minutos, revisa tu carpeta de correo no deseado.</p>
</section>
