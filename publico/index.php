<?php
declare(strict_types=1);

require_once __DIR__ . '/lib/datos.php';
require_once __DIR__ . '/lib/plantilla.php';
require_once __DIR__ . '/lib/correo.php';
require_once __DIR__ . '/lib/push.php';

date_default_timezone_set((string) (config()['zona'] ?? 'America/Mexico_City'));

$camino = trim((string) ($_GET['r'] ?? ($_SERVER['PATH_INFO'] ?? '')), '/');
$partes = $camino === '' ? [] : explode('/', $camino);
$metodo = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if (($partes[0] ?? '') === 'api') {
    require __DIR__ . '/api.php';
    exit;
}
if (($partes[0] ?? '') === 'admin') {
    require __DIR__ . '/admin.php';
    exit;
}

// --- avisos --------------------------------------------------------------

function aviso(string $titulo, string $texto, ?array $dep = null, int $codigo = 200): void
{
    http_response_code($codigo);
    render('mensaje', ['dep' => $dep, 'titulo_aviso' => $titulo, 'texto' => $texto],
        ['titulo' => $titulo]);
    exit;
}

function dependencia_o_404(string $clave): array
{
    $dep = dependencia($clave);
    if ($dep === null) {
        aviso('No encontramos esa oficina',
            'Revisa el enlace o el código QR que escaneaste.', null, 404);
    }
    return $dep;
}

// --- subida de archivos --------------------------------------------------

const EXTENSIONES = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx', 'txt'];
const MAX_BYTES = 8388608;      // 8 MB por archivo
const MAX_ARCHIVOS = 5;

function guardar_subidas(string $carpeta): array
{
    if (empty($_FILES['archivos']['name'][0])) {
        return [];
    }
    $destino = __DIR__ . '/subidas/' . $carpeta;
    if (!is_dir($destino) && !mkdir($destino, 0770, true) && !is_dir($destino)) {
        return [];
    }
    $guardados = [];
    $nombres = (array) $_FILES['archivos']['name'];
    foreach ($nombres as $indice => $nombre) {
        if (count($guardados) >= MAX_ARCHIVOS) {
            break;
        }
        if ((int) $_FILES['archivos']['error'][$indice] !== UPLOAD_ERR_OK) {
            continue;
        }
        $bytes = (int) $_FILES['archivos']['size'][$indice];
        $extension = mb_strtolower(pathinfo((string) $nombre, PATHINFO_EXTENSION));
        if ($bytes <= 0 || $bytes > MAX_BYTES || !in_array($extension, EXTENSIONES, true)) {
            continue;
        }
        $limpio = preg_replace('/[^A-Za-z0-9._-]+/', '-', (string) $nombre) ?: 'archivo';
        $ruta = $destino . '/' . substr(u_token(4), 0, 6) . '-' . mb_substr($limpio, 0, 80);
        if (move_uploaded_file((string) $_FILES['archivos']['tmp_name'][$indice], $ruta)
            || rename((string) $_FILES['archivos']['tmp_name'][$indice], $ruta)) {
            $guardados[] = [
                'nombre' => mb_substr((string) $nombre, 0, 160),
                'ruta' => 'subidas/' . $carpeta . '/' . basename($ruta),
                'tipo' => (string) ($_FILES['archivos']['type'][$indice] ?? ''),
                'bytes' => $bytes,
            ];
        }
    }
    return $guardados;
}

// --- rutas ---------------------------------------------------------------

if (!$partes) {
    render('inicio', ['dep' => null, 'lista' => dependencias()], ['titulo' => 'Citas']);
    exit;
}

// Mi turno: ver y cancelar.
if ($partes[0] === 't' && isset($partes[1])) {
    $turno = turno_por_token($partes[1]);
    if ($turno === null) {
        aviso('Ese turno ya no existe', 'Es posible que el enlace sea de otro día.', null, 404);
    }
    $dep = dependencia_id((int) $turno['dependencia_id']);
    if ($metodo === 'POST' && csrf_valido() && ($_POST['accion'] ?? '') === 'cancelar') {
        cancelar_turno($turno);
        u_redirigir(ruta('t/' . $turno['token']));
    }
    $estado = fila_estado($dep);
    $mio = null;
    $adelante = 0;
    foreach ($estado['turnos'] as $fila) {
        if ((int) $fila['id'] === (int) $turno['id']) {
            $mio = $fila;
            break;
        }
        if ($fila['estado'] === 'espera') {
            $adelante++;
        }
    }
    render('mi_turno', ['dep' => $dep, 'turno' => $mio ?? $turno, 'estado' => $estado,
                        'adelante' => $adelante], ['titulo' => 'Tu turno']);
    exit;
}

// Mi cita: ver y cancelar.
if ($partes[0] === 'c' && isset($partes[1])) {
    $cita = cita_por_token($partes[1]);
    if ($cita === null) {
        aviso('Esa solicitud ya no existe', 'Revisa el enlace que recibiste por correo.', null, 404);
    }
    $dep = dependencia_id((int) $cita['dependencia_id']);
    if ($metodo === 'POST' && csrf_valido() && ($_POST['accion'] ?? '') === 'cancelar') {
        cancelar_cita($cita);
        u_redirigir(ruta('c/' . $cita['token']));
    }
    render('mi_cita', ['dep' => $dep, 'cita' => cita_por_token($partes[1]),
                       'adjuntos' => adjuntos_de((int) $cita['id'])], ['titulo' => 'Tu solicitud']);
    exit;
}

$dep = dependencia_o_404($partes[0]);
$seccion = $partes[1] ?? '';

if ($seccion === 'fila') {
    render('fila', ['dep' => $dep, 'estado' => fila_estado($dep)], ['titulo' => 'La fila de hoy']);
    exit;
}

if ($seccion === 'pantalla') {
    render('pantalla', ['dep' => $dep, 'estado' => fila_estado($dep)],
        ['titulo' => 'Turnos', 'desnudo' => true]);
    exit;
}

if ($seccion === 'estado.json') {
    $estado = fila_estado($dep);
    $espera = array_slice($estado['espera'], 0, 6);
    u_json([
        'ahora' => $estado['ahora']->format('H:i'),
        'disponible' => $estado['atencion'] === 'atendiendo',
        'abierta' => $estado['abierta'],
        'atencion' => $estado['atencion'],
        'leyenda' => leyenda_atencion($estado),
        'disponible_hasta' => u_hora($estado['disponible_hasta']),
        'no_disponible_hasta' => u_hora($estado['no_disponible_hasta']),
        'mensaje' => $estado['motivo_cierre'],
        'actual' => $estado['actual'] ? [
            'folio' => (int) $estado['actual']['folio'],
            'nombre' => $estado['actual']['nombre_publico'] ?: u_nombre_corto($estado['actual']['nombre']),
        ] : null,
        'siguientes' => array_map(fn($t) => [
            'folio' => (int) $t['folio'],
            'nombre' => $t['nombre_publico'] ?: u_nombre_corto($t['nombre']),
            'hora' => $t['estimado'] ? u_hora($t['estimado']) : null,
        ], $espera),
        // El monitor de la entrada usa el horario para prender y apagar la pantalla.
        'horarios' => array_map(fn($h) => [
            'dia' => (int) $h['dia'], 'inicio' => $h['inicio'], 'fin' => $h['fin'],
        ], horarios((int) $dep['id'])),
    ]);
    exit;
}

// Horas libres para agendar, en JSON, cuando cambia la duracion elegida.
if ($seccion === '' && $metodo === 'GET' && isset($_GET['huecos'])) {
    $minutos = (int) $_GET['huecos'];
    if (!in_array($minutos, minutos_de_cita($dep), true)) {
        $minutos = minutos_de_cita($dep)[0];
    }
    u_json(['dias' => array_map(fn($dia) => [
        'etiqueta' => u_fecha_larga($dia['dia']->setTime(0, 0)),
        'opciones' => array_map(fn($o) => ['valor' => $o->format('Y-m-d H:i'), 'hora' => u_hora($o)],
            $dia['opciones']),
    ], huecos($dep, $minutos))]);
    exit;
}

// Paso 1: formulario de turno o de solicitud de reunion.
if ($seccion === '' && $metodo === 'GET') {
    render('turno', [
        'dep' => $dep,
        'estado' => fila_estado($dep),
        'huecos' => huecos($dep, minutos_de_cita($dep)[0]),
        'minutos_cita' => minutos_de_cita($dep),
        'datos' => [],
        'error' => (string) ($_GET['error'] ?? ''),
    ], ['titulo' => 'Tomar turno']);
    exit;
}

// Paso 2: validar la solicitud y mandar el codigo al correo.
if ($seccion === 'confirmar' && $metodo === 'POST') {
    if (!csrf_valido()) {
        aviso('La página caducó', 'Vuelve a llenar el formulario.', $dep, 400);
    }
    $tipo = ($_POST['tipo'] ?? 'turno') === 'cita' ? 'cita' : 'turno';
    $nombre = u_limpio($_POST['nombre'] ?? '', 120);
    $email = u_email($_POST['email'] ?? '');
    $asunto = u_limpio($_POST['asunto'] ?? '', 200);
    $estado = fila_estado($dep);

    $volver = function (string $error) use ($dep, $estado, $nombre, $email, $asunto) {
        render('turno', [
            'dep' => $dep, 'estado' => $estado,
            'huecos' => huecos($dep, minutos_de_cita($dep)[0]),
            'minutos_cita' => minutos_de_cita($dep),
            'datos' => ['nombre' => $nombre, 'email' => $email, 'asunto' => $asunto],
            'error' => $error,
        ], ['titulo' => 'Tomar turno']);
        exit;
    };

    if (mb_strlen($nombre) < 5) {
        $volver('Escribe tu nombre completo.');
    }
    if (!u_email_valido($email, (string) $dep['dominio_correo'])) {
        $volver('Necesitas un correo institucional @' . $dep['dominio_correo'] . '.');
    }
    if ($asunto === '') {
        $volver('Dinos en una línea de qué se trata.');
    }
    if (demasiadas_solicitudes($email, u_ip())) {
        $volver('Has hecho varias solicitudes seguidas. Inténtalo más tarde.');
    }

    if ($tipo === 'turno') {
        $minutos = (int) ($_POST['minutos'] ?? 0);
        if (!in_array($minutos, [5, (int) $dep['duracion_max']], true)) {
            $volver('Elige cuánto tiempo necesitas.');
        }
        if (!$estado['abierta']) {
            $volver($estado['motivo_cierre'] . ' Puedes solicitar una reunión.');
        }
        if (turnos_activos_de((int) $dep['id'], $email)) {
            $volver('Ya tienes un turno para hoy; revisa el enlace que te llegó por correo.');
        }
        $carga = compact('tipo', 'nombre', 'email', 'asunto', 'minutos');
    } else {
        $minutos = (int) ($_POST['minutos_cita'] ?? 0);
        if (!in_array($minutos, minutos_de_cita($dep), true)) {
            $volver('Elige la duración de la reunión.');
        }
        $propuesta = (string) ($_POST['hora'] ?? '');
        $valida = false;
        foreach (huecos($dep, $minutos) as $dia) {
            foreach ($dia['opciones'] as $opcion) {
                if ($opcion->format('Y-m-d H:i') === $propuesta) {
                    $valida = true;
                    break 2;
                }
            }
        }
        if (!$valida) {
            $volver('Esa hora ya no está libre. Elige otra de la lista.');
        }
        $carga = [
            'tipo' => 'cita',
            'nombre' => $nombre,
            'email' => $email,
            'asunto' => $asunto,
            'minutos' => $minutos,
            'propuesta' => $propuesta . ':00',
            'descripcion' => u_texto_largo($_POST['descripcion'] ?? '', 4000),
            'archivos' => guardar_subidas('pendientes/' . u_token(8)),
        ];
    }

    $verificacion = verificacion_crear($dep, $email, $carga);
    correo_codigo($dep, $email, $verificacion['codigo']);
    render('codigo', ['dep' => $dep, 'email' => $email, 'tipo' => $tipo, 'error' => ''],
        ['titulo' => 'Confirma tu correo']);
    exit;
}

// Paso 3: el codigo confirma y crea el turno o la solicitud.
if ($seccion === 'codigo' && $metodo === 'POST') {
    if (!csrf_valido()) {
        aviso('La página caducó', 'Vuelve a empezar.', $dep, 400);
    }
    $email = u_email($_POST['email'] ?? '');
    $carga = verificacion_comprobar($dep, $email, (string) ($_POST['codigo'] ?? ''));
    if ($carga === null) {
        render('codigo', ['dep' => $dep, 'email' => $email, 'tipo' => (string) ($_POST['tipo'] ?? 'turno'),
                          'error' => 'El código no coincide o ya venció.'],
            ['titulo' => 'Confirma tu correo']);
        exit;
    }

    if (($carga['tipo'] ?? 'turno') === 'turno') {
        $estado = fila_estado($dep);
        if (!$estado['abierta']) {
            aviso('La fila se cerró', $estado['motivo_cierre']
                . ' Puedes solicitar una reunión desde la página de la oficina.', $dep);
        }
        if (turnos_activos_de((int) $dep['id'], $email)) {
            aviso('Ya tienes un turno', 'Revisa el enlace que te llegó por correo.', $dep);
        }
        $turno = crear_turno($dep, $carga['nombre'], $email, $carga['asunto'], (int) $carga['minutos']);
        $nuevo = fila_estado($dep);
        $estimado = null;
        foreach ($nuevo['turnos'] as $fila) {
            if ((int) $fila['id'] === (int) $turno['id']) {
                $estimado = $fila['estimado'];
            }
        }
        correo_turno($dep, $turno, $estimado, url_absoluta('t/' . $turno['token']));
        push_turno_nuevo($dep, $turno, $estimado);   // el reloj vibra en tu muñeca
        u_redirigir(ruta('t/' . $turno['token']));
    }

    $cita = crear_cita($dep, $carga['nombre'], $email, $carga['asunto'],
        (string) ($carga['descripcion'] ?? ''), (int) $carga['minutos'], (string) $carga['propuesta']);
    foreach ((array) ($carga['archivos'] ?? []) as $archivo) {
        $origen = __DIR__ . '/' . $archivo['ruta'];
        $carpeta = __DIR__ . '/subidas/citas/' . $cita['id'];
        if (!is_dir($carpeta)) {
            mkdir($carpeta, 0770, true);
        }
        $destino = $carpeta . '/' . basename($archivo['ruta']);
        if (is_file($origen) && rename($origen, $destino)) {
            consulta('INSERT INTO adjuntos (cita_id, nombre, ruta, tipo, bytes, creado) '
                . 'VALUES (?, ?, ?, ?, ?, ?)',
                [$cita['id'], $archivo['nombre'], 'subidas/citas/' . $cita['id'] . '/' . basename($destino),
                 $archivo['tipo'], $archivo['bytes'], ahora_texto()]);
        }
    }
    correo_cita_solicitada($dep, $cita, url_absoluta('c/' . $cita['token']));
    u_redirigir(ruta('c/' . $cita['token']));
}

function url_absoluta(string $destino): string
{
    $esquema = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $host = (string) ($_SERVER['HTTP_HOST'] ?? (config()['host'] ?? 'localhost'));
    return $esquema . '://' . $host . ruta($destino);
}

aviso('Página no encontrada', 'Revisa el enlace.', $dep ?? null, 404);
