<?php
declare(strict_types=1);

/**
 * API que usa la laptop del titular. Autenticacion con el token de la
 * dependencia:  Authorization: Bearer <token>   y  ?d=<clave>
 */

require_once __DIR__ . '/lib/datos.php';
require_once __DIR__ . '/lib/correo.php';

date_default_timezone_set((string) (config()['zona'] ?? 'America/Mexico_City'));

function api_token(): string
{
    $cabecera = (string) ($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
    if (stripos($cabecera, 'bearer ') === 0) {
        return trim(substr($cabecera, 7));
    }
    return (string) ($_GET['token'] ?? '');
}

/**
 * El reloj trae su propia llave, que solo sirve para leer su vista. Asi, si se
 * pierde el reloj, se regenera esa llave sin tocar la de la laptop, y con ella
 * nadie puede llamar turnos ni cancelar nada.
 */
function api_dependencia(string $accion = ''): array
{
    $clave = (string) ($_GET['d'] ?? '');
    $dep = $clave === '' ? null : dependencia($clave);
    $token = api_token();
    if ($dep === null || $token === '') {
        u_json(['error' => 'no autorizado'], 401);
        exit;
    }

    if (!token_permite($dep, $token, $accion)) {
        u_json(['error' => 'no autorizado'], 401);
        exit;
    }
    return $dep;
}

function api_cuerpo(): array
{
    $crudo = file_get_contents('php://input') ?: '';
    $datos = json_decode($crudo, true);
    return is_array($datos) ? $datos : $_POST;
}

function api_turno(array $turno, ?DateTimeImmutable $estimado): array
{
    return [
        'id' => (int) $turno['id'],
        'folio' => (int) $turno['folio'],
        'nombre' => $turno['nombre'],
        'nombre_publico' => $turno['nombre_publico'],
        'email' => $turno['email'],
        'asunto' => $turno['asunto'],
        'minutos' => (int) $turno['minutos'],
        'estado' => $turno['estado'],
        'creado' => $turno['creado'],
        'llamado' => $turno['llamado'],
        'estimado' => $estimado ? $estimado->format('Y-m-d H:i:s') : null,
        'espera' => $turno['espera'] ?? null,
        'restan' => $turno['restan'] ?? null,
        'transcurridos' => $turno['transcurridos'] ?? null,
    ];
}

/** Avisa por correo a quien se le recorrio mucho la hora estimada. */
function avisar_recorridos(array $dep, array $estado, int $margen = 15): int
{
    $enlaceBase = rtrim((string) (config()['sitio'] ?? ''), '/');
    $silencio = $estado['ahora']->modify('-10 minutes');
    $avisados = 0;

    foreach ($estado['turnos'] as $turno) {
        if ($turno['estado'] !== 'espera' || $turno['estimado'] === null) {
            continue;
        }
        $anterior = a_momento($turno['estimado_guardado']);
        if ($anterior === null) {
            continue;                       // aun no habia hora que comparar
        }
        $ultimoAviso = a_momento($turno['avisado']);
        if ($ultimoAviso !== null && $ultimoAviso > $silencio) {
            continue;                       // no lo bombardeamos a correos
        }
        $diferencia = abs($turno['estimado']->getTimestamp() - $anterior->getTimestamp()) / 60;
        if ($diferencia < $margen) {
            continue;
        }
        correo_recorrido($dep, $turno, $turno['estimado'], $enlaceBase . '/t/' . $turno['token']);
        consulta('UPDATE turnos SET avisado = ? WHERE id = ?', [ahora_texto(), $turno['id']]);
        $avisados++;
    }
    return $avisados;
}

/** Guarda la hora estimada para poder comparar en la siguiente vuelta. */
function guardar_estimados(array $estado): void
{
    foreach ($estado['turnos'] as $turno) {
        if ($turno['estado'] !== 'espera') {
            continue;
        }
        $nuevo = $turno['estimado'] ? $turno['estimado']->format('Y-m-d H:i:s') : null;
        if ($nuevo !== $turno['estimado_guardado']) {
            consulta('UPDATE turnos SET estimado = ? WHERE id = ?', [$nuevo, $turno['id']]);
        }
    }
}

$accion = (string) ($_GET['accion'] ?? 'estado');
$dep = api_dependencia($accion);
$cuerpo = api_cuerpo();

if ($accion === 'estado') {
    $estado = fila_estado($dep);
    $enviados = avisar_recorridos($dep, $estado);
    guardar_estimados($estado);

    $solicitudes = [];
    foreach (citas((int) $dep['id'], 'solicitada') as $cita) {
        $cita['adjuntos'] = adjuntos_de((int) $cita['id']);
        $solicitudes[] = $cita;
    }
    $aprobadas = citas_confirmadas((int) $dep['id'], 50);

    u_json([
        'dependencia' => [
            'clave' => $dep['clave'], 'nombre' => $dep['nombre'], 'titular' => $dep['titular'],
            'disponible' => (int) $dep['disponible'] === 1, 'mensaje' => $dep['mensaje'],
            'duracion_max' => (int) $dep['duracion_max'],
            'colchon_turno' => (int) $dep['colchon_turno'],
            'colchon_reunion' => (int) $dep['colchon_reunion'],
            'minutos_cita' => minutos_de_cita($dep),
        ],
        'ahora' => $estado['ahora']->format('Y-m-d H:i:s'),
        'abierta' => $estado['abierta'],
        'atencion' => $estado['atencion'],
        'jornada' => $estado['jornada'],
        'disponible_hasta' => $estado['disponible_hasta']
            ? $estado['disponible_hasta']->format('Y-m-d H:i:s') : null,
        'no_disponible_hasta' => $estado['no_disponible_hasta']
            ? $estado['no_disponible_hasta']->format('Y-m-d H:i:s') : null,
        'motivo_cierre' => $estado['motivo_cierre'],
        'proximo_hueco' => $estado['proximo_hueco'] ? $estado['proximo_hueco']->format('Y-m-d H:i:s') : null,
        'turnos' => array_map(fn($t) => api_turno($t, $t['estimado']), $estado['turnos']),
        'bloqueos' => array_map(fn($b) => [
            'id' => (int) $b['id'], 'inicio' => $b['inicio']->format('Y-m-d H:i:s'),
            'fin' => $b['fin']->format('Y-m-d H:i:s'), 'motivo' => $b['motivo'],
            'origen' => $b['origen'], 'cita_id' => $b['cita_id'] ? (int) $b['cita_id'] : null,
        ], $estado['bloqueos']),
        'horarios' => horarios((int) $dep['id']),
        'citas' => $solicitudes,
        'citas_aprobadas' => $aprobadas,
        'avisos_enviados' => $enviados,
    ]);
    exit;
}

// --- jornada -------------------------------------------------------------

if ($accion === 'abrir') {
    $jornada = abrir_jornada($dep, $cuerpo['cierre'] ?? null, $cuerpo['tope'] ?? null,
        $cuerpo['fecha'] ?? null, $cuerpo['apertura'] ?? null);
    consulta('UPDATE dependencias SET disponible = 1, mensaje = ? WHERE id = ?',
        [u_limpio($cuerpo['mensaje'] ?? '', 255), $dep['id']]);
    u_json(['ok' => true, 'jornada' => $jornada]);
    exit;
}

if ($accion === 'cerrar') {
    $jornada = cerrar_jornada($dep, (string) ($cuerpo['nota'] ?? ''), $cuerpo['fecha'] ?? null);
    consulta('UPDATE dependencias SET disponible = 0 WHERE id = ?', [$dep['id']]);
    u_json(['ok' => true, 'jornada' => $jornada]);
    exit;
}

if ($accion === 'jornada') {
    $fecha = (string) ($cuerpo['fecha'] ?? $_GET['fecha'] ?? (new DateTimeImmutable('now'))->format('Y-m-d'));
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'GET') {
        u_json(['jornada' => jornada($dep, $fecha, true)]);
        exit;
    }
    $datos = [];
    foreach (['apertura', 'cierre', 'estado', 'nota'] as $campo) {
        if (isset($cuerpo[$campo])) {
            $datos[$campo] = (string) $cuerpo[$campo];
        }
    }
    if (array_key_exists('tope', $cuerpo)) {
        $datos['tope'] = $cuerpo['tope'] ?: null;
    }
    u_json(['ok' => true, 'jornada' => configurar_jornada($dep, $fecha, $datos)]);
    exit;
}

/** Un rato sin atender: clase, videoconferencia, comida o simple concentracion. */
if ($accion === 'pausar') {
    $ahora = new DateTimeImmutable('now');
    $hasta = a_momento((string) ($cuerpo['hasta'] ?? ''));
    if ($hasta === null && !empty($cuerpo['minutos'])) {
        $hasta = $ahora->modify('+' . max(1, (int) $cuerpo['minutos']) . ' minutes');
    }
    if ($hasta === null || $hasta <= $ahora) {
        u_json(['error' => 'indica hasta que hora'], 400);
        exit;
    }
    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen) VALUES (?, ?, ?, ?, ?)',
        [$dep['id'], $ahora->format('Y-m-d H:i:s'), $hasta->format('Y-m-d H:i:s'),
         u_limpio($cuerpo['motivo'] ?? 'No disponible', 160), 'manual']);
    evento((int) $dep['id'], 'pausa', u_hora($hasta));
    u_json(['ok' => true, 'hasta' => $hasta->format('Y-m-d H:i:s')]);
    exit;
}

/** Salida de emergencia: se cancela la cola y se avisa a cada quien. */
if ($accion === 'cancelar_cola') {
    $motivo = u_limpio($cuerpo['motivo'] ?? '', 160);
    $cerrar = !isset($cuerpo['cerrar']) || !empty($cuerpo['cerrar']);
    $afectados = cancelar_cola($dep, $motivo, $cerrar);
    $enlace = rtrim((string) (config()['sitio'] ?? ''), '/') . '/' . $dep['clave'];
    foreach ($afectados as $turno) {
        correo_cola_cancelada($dep, $turno, $motivo, $enlace);
    }
    if ($cerrar) {
        consulta('UPDATE dependencias SET disponible = 0 WHERE id = ?', [$dep['id']]);
    }
    u_json(['ok' => true, 'cancelados' => count($afectados),
            'avisados' => array_map(fn($t) => $t['email'], $afectados)]);
    exit;
}

if ($accion === 'disponible') {
    // Compatibilidad: prender equivale a abrir la jornada y apagar a cerrarla.
    if (!empty($cuerpo['disponible'])) {
        abrir_jornada($dep);
    } else {
        cerrar_jornada($dep, (string) ($cuerpo['mensaje'] ?? ''));
    }
    consulta('UPDATE dependencias SET disponible = ?, mensaje = ? WHERE id = ?',
        [!empty($cuerpo['disponible']) ? 1 : 0, u_limpio($cuerpo['mensaje'] ?? '', 255), $dep['id']]);
    u_json(['ok' => true]);
    exit;
}

if ($accion === 'horarios') {
    db()->beginTransaction();
    consulta('DELETE FROM horarios WHERE dependencia_id = ?', [$dep['id']]);
    foreach ((array) ($cuerpo['horarios'] ?? []) as $tramo) {
        $dia = (int) ($tramo['dia'] ?? 0);
        if ($dia < 1 || $dia > 7) {
            continue;
        }
        consulta('INSERT INTO horarios (dependencia_id, dia, inicio, fin) VALUES (?, ?, ?, ?)',
            [$dep['id'], $dia, substr((string) $tramo['inicio'], 0, 5), substr((string) $tramo['fin'], 0, 5)]);
    }
    if (isset($cuerpo['excepciones'])) {
        consulta('DELETE FROM excepciones WHERE dependencia_id = ? AND fecha >= ?',
            [$dep['id'], (new DateTimeImmutable('now'))->format('Y-m-d')]);
        foreach ((array) $cuerpo['excepciones'] as $excepcion) {
            consulta('INSERT INTO excepciones (dependencia_id, fecha, tipo, inicio, fin, motivo) '
                . 'VALUES (?, ?, ?, ?, ?, ?)',
                [$dep['id'], (string) $excepcion['fecha'], (string) ($excepcion['tipo'] ?? 'cerrado'),
                 $excepcion['inicio'] ?? null, $excepcion['fin'] ?? null,
                 u_limpio($excepcion['motivo'] ?? '', 160)]);
        }
    }
    db()->commit();
    u_json(['ok' => true, 'horarios' => horarios((int) $dep['id'])]);
    exit;
}

if ($accion === 'bloqueo') {
    if (!empty($cuerpo['eliminar'])) {
        consulta('DELETE FROM bloqueos WHERE id = ? AND dependencia_id = ? AND origen = ?',
            [(int) $cuerpo['eliminar'], $dep['id'], 'manual']);
        u_json(['ok' => true]);
        exit;
    }
    $inicio = a_momento((string) ($cuerpo['inicio'] ?? ''));
    $fin = a_momento((string) ($cuerpo['fin'] ?? ''));
    if ($inicio === null || $fin === null || $fin <= $inicio) {
        u_json(['error' => 'fechas invalidas'], 400);
        exit;
    }
    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen) VALUES (?, ?, ?, ?, ?)',
        [$dep['id'], $inicio->format('Y-m-d H:i:s'), $fin->format('Y-m-d H:i:s'),
         u_limpio($cuerpo['motivo'] ?? 'Reunión', 160), 'manual']);
    u_json(['ok' => true, 'id' => (int) db()->lastInsertId()]);
    exit;
}

if ($accion === 'turno') {
    $turno = fila_una('SELECT * FROM turnos WHERE id = ? AND dependencia_id = ?',
        [(int) ($cuerpo['id'] ?? 0), $dep['id']]);
    if ($turno === null) {
        u_json(['error' => 'turno no encontrado'], 404);
        exit;
    }
    switch ((string) ($cuerpo['accion'] ?? '')) {
        case 'llamar':
            consulta('UPDATE turnos SET estado = ?, llamado = ? WHERE dependencia_id = ? AND estado = ?',
                ['ausente', ahora_texto(), $dep['id'], 'llamado']);   // solo uno a la vez
            consulta('UPDATE turnos SET estado = ?, llamado = ?, nombre_publico = ? WHERE id = ?',
                ['llamado', ahora_texto(),
                 u_limpio($cuerpo['nombre_publico'] ?? $turno['nombre_publico'], 120), $turno['id']]);
            consulta('UPDATE dependencias SET atendiendo_turno = ? WHERE id = ?', [$turno['id'], $dep['id']]);
            break;
        case 'atendido':
            consulta('UPDATE turnos SET estado = ?, cerrado = ? WHERE id = ?',
                ['atendido', ahora_texto(), $turno['id']]);
            break;
        case 'ausente':
            consulta('UPDATE turnos SET estado = ?, cerrado = ? WHERE id = ?',
                ['ausente', ahora_texto(), $turno['id']]);
            break;
        case 'cancelar':
            cancelar_turno($turno, 'titular');
            break;
        default:
            u_json(['error' => 'accion desconocida'], 400);
            exit;
    }
    u_json(['ok' => true]);
    exit;
}

if ($accion === 'cita') {
    $cita = fila_una('SELECT * FROM citas WHERE id = ? AND dependencia_id = ?',
        [(int) ($cuerpo['id'] ?? 0), $dep['id']]);
    if ($cita === null) {
        u_json(['error' => 'cita no encontrada'], 404);
        exit;
    }
    $enlace = (string) (config()['sitio'] ?? '') . '/c/' . $cita['token'];
    if ((string) ($cuerpo['accion'] ?? '') === 'aprobar') {
        $resuelta = aprobar_cita($cita, $cuerpo['inicio'] ?? null, u_limpio($cuerpo['motivo'] ?? '', 255));
        correo_cita_resuelta($dep, $resuelta, $enlace);
    } elseif ((string) ($cuerpo['accion'] ?? '') === 'rechazar') {
        $resuelta = rechazar_cita($cita, u_limpio($cuerpo['motivo'] ?? '', 255));
        correo_cita_resuelta($dep, $resuelta, $reagendar);
    } elseif ((string) ($cuerpo['accion'] ?? '') === 'cancelar') {
        $motivo = u_limpio($cuerpo['motivo'] ?? '', 255);
        cancelar_cita($cita, 'titular');
        $resuelta = cita_por_token((string) $cita['token']);
        correo_cita_cancelada($dep, $cita, $motivo, $reagendar);
    } else {
        u_json(['error' => 'accion desconocida'], 400);
        exit;
    }
    u_json(['ok' => true, 'cita' => $resuelta]);
    exit;
}

/**
 * Vista minima para el reloj: quien sigue y cuanto falta de lo que estas
 * atendiendo. Se consulta seguido, asi que responde lo menos posible.
 */
if ($accion === 'reloj') {
    $estado = fila_estado($dep);
    $esperando = $estado['espera'];
    $siguiente = $esperando[0] ?? null;
    $actual = $estado['actual'];

    u_json([
        'ahora' => $estado['ahora']->format('H:i'),
        'atencion' => $estado['atencion'],
        'leyenda' => leyenda_atencion($estado),
        'abierta' => $estado['abierta'],
        'esperando' => count($esperando),
        'actual' => $actual ? [
            'folio' => (int) $actual['folio'],
            'nombre' => u_nombre_corto((string) $actual['nombre']),
            'minutos' => (int) $actual['minutos'],
            'transcurridos' => (int) $actual['transcurridos'],
            'restan' => (int) $actual['restan'],
            'excedido' => ((int) $actual['restan']) < 0,
        ] : null,
        'siguiente' => $siguiente ? [
            'folio' => (int) $siguiente['folio'],
            'nombre' => u_nombre_corto((string) $siguiente['nombre']),
            'asunto' => (string) $siguiente['asunto'],
            'hora' => $siguiente['estimado'] ? u_hora($siguiente['estimado']) : null,
            'espera' => $siguiente['espera'],
        ] : null,
    ]);
    exit;
}

// --- minutas -------------------------------------------------------------

if ($accion === 'minuta') {
    if (empty($_FILES['archivo']['tmp_name']) || (int) $_FILES['archivo']['error'] !== UPLOAD_ERR_OK) {
        u_json(['error' => 'falta el archivo de la minuta'], 400);
        exit;
    }
    $temporal = (string) $_FILES['archivo']['tmp_name'];
    if ((int) $_FILES['archivo']['size'] > 10485760) {
        u_json(['error' => 'la minuta pesa demasiado'], 400);
        exit;
    }
    if (strtolower(pathinfo((string) $_FILES['archivo']['name'], PATHINFO_EXTENSION)) !== 'pdf') {
        u_json(['error' => 'solo se aceptan minutas en PDF'], 400);
        exit;
    }
    $guardado = carpeta_subidas() . '/minutas/tmp-' . u_token(8) . '.pdf';
    if (!is_dir(dirname($guardado))) {
        mkdir(dirname($guardado), 0770, true);
    }
    if (!move_uploaded_file($temporal, $guardado) && !rename($temporal, $guardado)) {
        u_json(['error' => 'no se pudo recibir el archivo'], 500);
        exit;
    }
    try {
        $minuta = guardar_minuta($dep, [
            'persona' => $_POST['persona'] ?? '',
            'email' => $_POST['email'] ?? '',
            'asunto' => $_POST['asunto'] ?? '',
            'fecha' => $_POST['fecha'] ?? '',
            'reunion_local' => isset($_POST['reunion_local']) ? (int) $_POST['reunion_local'] : null,
        ], $guardado);
    } catch (Throwable $error) {
        @unlink($guardado);
        u_json(['error' => $error->getMessage()], 500);
        exit;
    }
    u_json(['ok' => true, 'minuta' => $minuta]);
    exit;
}

if ($accion === 'minuta_enviar') {
    $registro = minuta((int) ($cuerpo['id'] ?? 0), (int) $dep['id']);
    if ($registro === null) {
        u_json(['error' => 'esa minuta no esta en el servidor'], 404);
        exit;
    }
    $destinatario = u_email($cuerpo['destinatario'] ?? $registro['email']);
    if (!filter_var($destinatario, FILTER_VALIDATE_EMAIL)) {
        u_json(['error' => 'el destinatario no es valido'], 400);
        exit;
    }
    $enviado = correo_minuta($dep, $registro, $destinatario, (string) ($cuerpo['mensaje'] ?? ''));
    marcar_minuta((int) $registro['id'], $enviado, $destinatario,
        $enviado ? 'enviada desde el servidor' : 'el servidor de correo no acepto el mensaje');
    evento((int) $dep['id'], $enviado ? 'minuta-enviada' : 'minuta-error', $destinatario);
    if (!$enviado) {
        u_json(['error' => 'el servidor de correo no acepto el mensaje',
                'minuta' => minuta((int) $registro['id'], (int) $dep['id'])], 502);
        exit;
    }
    u_json(['ok' => true, 'minuta' => minuta((int) $registro['id'], (int) $dep['id'])]);
    exit;
}

if ($accion === 'minutas') {
    limpiar_minutas($dep);
    u_json(['minutas' => minutas_de((int) $dep['id'], (string) ($_GET['email'] ?? ''))]);
    exit;
}

if ($accion === 'minuta_borrar') {
    $registro = minuta((int) ($cuerpo['id'] ?? 0), (int) $dep['id']);
    if ($registro === null) {
        u_json(['error' => 'esa minuta no esta en el servidor'], 404);
        exit;
    }
    borrar_minuta($registro);
    u_json(['ok' => true]);
    exit;
}

if ($accion === 'minuta_descargar') {
    $registro = minuta((int) ($_GET['id'] ?? 0), (int) $dep['id']);
    $ruta = $registro ? ruta_subida((string) $registro['archivo']) : '';
    if (!$registro || !is_file($ruta)) {
        u_json(['error' => 'esa minuta no esta en el servidor'], 404);
        exit;
    }
    header('Content-Type: application/pdf');
    header('Content-Disposition: attachment; filename="' . $registro['nombre'] . '"');
    readfile($ruta);
    exit;
}

if ($accion === 'adjunto') {
    $adjunto = fila_una('SELECT a.* FROM adjuntos a JOIN citas c ON c.id = a.cita_id '
        . 'WHERE a.id = ? AND c.dependencia_id = ?', [(int) ($_GET['id'] ?? 0), $dep['id']]);
    $ruta = $adjunto ? __DIR__ . '/' . $adjunto['ruta'] : '';
    if (!$adjunto || !is_file($ruta)) {
        u_json(['error' => 'adjunto no encontrado'], 404);
        exit;
    }
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . basename($adjunto['nombre']) . '"');
    readfile($ruta);
    exit;
}

u_json(['error' => 'accion desconocida'], 400);
