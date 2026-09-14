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

function api_dependencia(): array
{
    $clave = (string) ($_GET['d'] ?? '');
    $dep = $clave === '' ? null : dependencia($clave);
    $token = api_token();
    if ($dep === null || $token === '' || !hash_equals((string) $dep['token_hash'], hash('sha256', $token))) {
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

$dep = api_dependencia();
$accion = (string) ($_GET['accion'] ?? 'estado');
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
    $aprobadas = filas('SELECT * FROM citas WHERE dependencia_id = ? AND estado = ? AND propuesta >= ? '
        . 'ORDER BY confirmada LIMIT 50',
        [$dep['id'], 'aprobada', (new DateTimeImmutable('now'))->modify('-1 day')->format('Y-m-d H:i:s')]);

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

if ($accion === 'disponible') {
    consulta('UPDATE dependencias SET disponible = ?, mensaje = ? WHERE id = ?',
        [!empty($cuerpo['disponible']) ? 1 : 0, u_limpio($cuerpo['mensaje'] ?? '', 255), $dep['id']]);
    evento((int) $dep['id'], 'disponibilidad', !empty($cuerpo['disponible']) ? 'disponible' : 'no disponible');
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
        correo_cita_resuelta($dep, $resuelta, $enlace);
    } else {
        u_json(['error' => 'accion desconocida'], 400);
        exit;
    }
    u_json(['ok' => true, 'cita' => $resuelta]);
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
