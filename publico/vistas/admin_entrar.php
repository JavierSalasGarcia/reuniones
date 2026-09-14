<section class="tarjeta angosta">
  <h1>Administración</h1>
  <?php if ($sin_hash): ?>
    <p class="error">Falta <code>admin_hash</code> en config.php. Genera uno con:</p>
    <pre class="texto">php -r "echo password_hash('tu contraseña', PASSWORD_DEFAULT);"</pre>
  <?php else: ?>
    <?php if ($error): ?><p class="error"><?= u_escapar($error) ?></p><?php endif; ?>
    <form method="post" class="formulario">
      <?= campo_csrf() ?>
      <input type="hidden" name="accion" value="entrar">
      <label>Contraseña <input type="password" name="clave" required autofocus></label>
      <button class="grande">Entrar</button>
    </form>
  <?php endif; ?>
</section>
