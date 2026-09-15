<?php
declare(strict_types=1);

/** Panel para dar de alta dependencias y generar el acceso de cada titular. */

require_once __DIR__ . '/lib/datos.php';
require_once __DIR__ . '/lib/plantilla.php';

date_default_timezone_set((string) (config()['zona'] ?? 'America/Mexico_City'));

if (session_status() !== PHP_SESSION_ACTIVE) {
    session_start();
}

$hash = (string) (config()['admin_hash'] ?? '');
$metodo = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if (($_GET['salir'] ?? '') === '1') {
    unset($_SESSION['admin']);
    u_redirigir(ruta('admin'));
}

if (empty($_SESSION['admin'])) {
    $error = '';
    if ($metodo === 'POST' && ($_POST['accion'] ?? '') === 'entrar') {
        if ($hash !== '' && password_verify((string) ($_POST['clave'] ?? ''), $hash)) {
            session_regenerate_id(true);
            $_SESSION['admin'] = true;
            u_redirigir(ruta('admin'));
        }
        $error = 'Contraseña incorrecta.';
        usleep(400000);
    }
    render('admin_entrar', ['dep' => null, 'error' => $error, 'sin_hash' => $hash === ''],
        ['titulo' => 'Administración']);
    exit;
}

$mensaje = '';
$token_nuevo = '';

if ($metodo === 'POST' && csrf_valido()) {
    $accion = (string) ($_POST['accion'] ?? '');

    if ($accion === 'crear') {
        $clave = mb_strtolower(preg_replace('/[^a-z0-9]+/i', '', (string) ($_POST['clave'] ?? '')) ?? '');
        $nombre = u_limpio($_POST['nombre'] ?? '', 120);
        $titular = u_limpio($_POST['titular'] ?? '', 120);
        if ($clave === '' || $nombre === '' || $titular === '') {
            $mensaje = 'Faltan datos de la dependencia.';
        } elseif (fila_una('SELECT id FROM dependencias WHERE clave = ?', [$clave])) {
            $mensaje = "La clave «{$clave}» ya existe.";
        } else {
            $token = u_token(20);
            consulta('INSERT INTO dependencias (clave, nombre, titular, correo_titular, dominio_correo, '
                . 'token_hash, push_tema, disponible, creado) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)',
                [$clave, $nombre, $titular, u_email($_POST['correo'] ?? ''),
                 u_limpio($_POST['dominio'] ?? 'uaemex.mx', 80), hash('sha256', $token),
                 $clave . '-' . u_token(8), ahora_texto()]);
            $token_nuevo = $token;
            $mensaje = "Dependencia «{$clave}» creada. Copia el token: solo se muestra una vez.";
            evento(null, 'alta-dependencia', $clave);
        }
    }

    if ($accion === 'editar') {
        $id = (int) ($_POST['id'] ?? 0);
        consulta('UPDATE dependencias SET nombre = ?, titular = ?, correo_titular = ?, dominio_correo = ?, '
            . 'duracion_max = ?, colchon_turno = ?, colchon_reunion = ?, minutos_cita = ?, '
            . 'push_tema = ?, push_detalle = ?, push_avisos = ?, activa = ? WHERE id = ?',
            [u_limpio($_POST['nombre'] ?? '', 120), u_limpio($_POST['titular'] ?? '', 120),
             u_email($_POST['correo'] ?? ''), u_limpio($_POST['dominio'] ?? 'uaemex.mx', 80),
             max(1, (int) ($_POST['duracion_max'] ?? 10)), max(0, (int) ($_POST['colchon_turno'] ?? 2)),
             max(0, (int) ($_POST['colchon_reunion'] ?? 10)),
             u_limpio($_POST['minutos_cita'] ?? '20,30,45', 40),
             u_limpio($_POST['push_tema'] ?? '', 80), empty($_POST['push_detalle']) ? 0 : 1,
             implode(',', array_intersect(
                 ['formado', 'excedido', 'cita', 'vacia'],
                 array_map('strval', (array) ($_POST['push_avisos'] ?? [])))),
             empty($_POST['activa']) ? 0 : 1, $id]);
        $mensaje = 'Datos actualizados.';
    }

    if ($accion === 'token') {
        $id = (int) ($_POST['id'] ?? 0);
        $token_nuevo = u_token(20);
        consulta('UPDATE dependencias SET token_hash = ? WHERE id = ?', [hash('sha256', $token_nuevo), $id]);
        $mensaje = 'Token regenerado. El anterior dejó de servir.';
        evento($id, 'token', 'regenerado');
    }

    if ($accion === 'token-reloj') {
        $id = (int) ($_POST['id'] ?? 0);
        $token_nuevo = u_token(20);
        consulta('UPDATE dependencias SET token_reloj_hash = ? WHERE id = ?',
            [hash('sha256', $token_nuevo), $id]);
        $mensaje = 'Llave del reloj regenerada. Ponla en local.properties y vuelve a instalar la app.';
        evento($id, 'token-reloj', 'regenerado');
    }
}

render('admin', [
    'dep' => null,
    'lista' => dependencias(),
    'mensaje' => $mensaje,
    'token_nuevo' => $token_nuevo,
], ['titulo' => 'Administración']);
