<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= u_escapar($titulo) ?><?= $dep ? ' · ' . u_escapar($dep['nombre']) : '' ?></title>
<link rel="stylesheet" href="<?= ruta('estatico/estilo.css') ?>">
</head>
<body class="<?= $desnudo ? 'kiosco' : '' ?>">
<?php if (!$desnudo): ?>
<header class="barra">
  <a class="marca" href="<?= $dep ? ruta($dep['clave']) : ruta() ?>">
    <?= $dep ? u_escapar($dep['nombre']) : 'Citas' ?>
  </a>
  <?php if ($dep): ?>
  <nav>
    <a href="<?= ruta($dep['clave']) ?>">Tomar turno</a>
    <a href="<?= ruta($dep['clave'] . '/fila') ?>">Ver la fila</a>
  </nav>
  <?php endif; ?>
</header>
<?php endif; ?>
<main class="<?= $desnudo ? 'pantalla' : '' ?>"><?= $contenido ?></main>
<?php if (!$desnudo && $dep): ?>
<footer><?= u_escapar($dep['titular']) ?> · Facultad de Ingeniería</footer>
<?php endif; ?>
</body>
</html>
