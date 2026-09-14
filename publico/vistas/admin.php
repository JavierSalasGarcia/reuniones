<section class="tarjeta">
  <h1>Dependencias</h1>
  <p class="meta">Cada una tiene su propia fila, su pantalla y su token de acceso para la laptop.
    <a href="<?= ruta('admin?salir=1') ?>">Salir</a></p>

  <?php if ($mensaje): ?><p class="estado aviso"><?= u_escapar($mensaje) ?></p><?php endif; ?>
  <?php if ($token_nuevo): ?>
    <p class="estado bien">Token: <code class="token"><?= u_escapar($token_nuevo) ?></code></p>
    <p class="meta">Guárdalo en el archivo <code>.env</code> de la laptop como
      <code>REUNIONES_NUBE_TOKEN</code>. No se vuelve a mostrar.</p>
  <?php endif; ?>

  <?php foreach ($lista as $fila): ?>
  <article class="dependencia">
    <h2><?= u_escapar($fila['nombre']) ?> <span class="etiqueta"><?= u_escapar($fila['clave']) ?></span></h2>
    <p class="meta">
      <a href="<?= ruta($fila['clave']) ?>">Página pública</a> ·
      <a href="<?= ruta($fila['clave'] . '/fila') ?>">Fila</a> ·
      <a href="<?= ruta($fila['clave'] . '/pantalla') ?>">Pantalla del monitor</a> ·
      <?= (int) $fila['disponible'] === 1 ? 'disponible ahora' : 'no disponible' ?>
    </p>
    <form method="post" class="formulario compacto">
      <?= campo_csrf() ?>
      <input type="hidden" name="accion" value="editar">
      <input type="hidden" name="id" value="<?= (int) $fila['id'] ?>">
      <label>Nombre <input name="nombre" value="<?= u_escapar($fila['nombre']) ?>"></label>
      <label>Titular <input name="titular" value="<?= u_escapar($fila['titular']) ?>"></label>
      <label>Correo del titular <input name="correo" type="email" value="<?= u_escapar($fila['correo_titular']) ?>"></label>
      <label>Dominio aceptado <input name="dominio" value="<?= u_escapar($fila['dominio_correo']) ?>"></label>
      <div class="en-linea">
        <label>Minutos por turno <input name="duracion_max" type="number" min="1" max="30"
               value="<?= (int) $fila['duracion_max'] ?>"></label>
        <label>Colchón entre turnos <input name="colchon_turno" type="number" min="0" max="30"
               value="<?= (int) $fila['colchon_turno'] ?>"></label>
        <label>Colchón antes de reunión <input name="colchon_reunion" type="number" min="0" max="60"
               value="<?= (int) $fila['colchon_reunion'] ?>"></label>
        <label>Duraciones de reunión <input name="minutos_cita" value="<?= u_escapar($fila['minutos_cita']) ?>"></label>
      </div>
      <label>Tema de avisos al celular (ntfy)
        <input name="push_tema" value="<?= u_escapar($fila['push_tema']) ?>"></label>
      <label class="casilla"><input type="checkbox" name="push_detalle" value="1"
             <?= (int) $fila['push_detalle'] === 1 ? 'checked' : '' ?>>
        Incluir nombre y asunto en el aviso</label>
      <label class="casilla"><input type="checkbox" name="activa" value="1"
             <?= (int) $fila['activa'] === 1 ? 'checked' : '' ?>> Activa</label>
      <button class="secundario">Guardar</button>
    </form>
    <form method="post" onsubmit="return confirm('El token actual dejará de funcionar. ¿Continuar?')">
      <?= campo_csrf() ?>
      <input type="hidden" name="accion" value="token">
      <input type="hidden" name="id" value="<?= (int) $fila['id'] ?>">
      <button class="secundario">Regenerar token</button>
    </form>
  </article>
  <?php endforeach; ?>

  <article class="dependencia">
    <h2>Agregar dependencia</h2>
    <form method="post" class="formulario compacto">
      <?= campo_csrf() ?>
      <input type="hidden" name="accion" value="crear">
      <label>Clave (la que va en la dirección: sa, dir, …)
        <input name="clave" required maxlength="16" pattern="[A-Za-z0-9]+"></label>
      <label>Nombre <input name="nombre" required placeholder="Subdirección Académica"></label>
      <label>Titular <input name="titular" required></label>
      <label>Correo del titular <input name="correo" type="email"></label>
      <label>Dominio aceptado <input name="dominio" value="uaemex.mx"></label>
      <button>Crear</button>
    </form>
  </article>
</section>
