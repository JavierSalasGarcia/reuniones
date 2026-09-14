<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/agenda.php';
require_once __DIR__ . '/util.php';

/** Consultas de la parte publica: dependencias, fila, turnos y citas. */

function dependencia(string $clave): ?array
{
    return fila_una('SELECT * FROM dependencias WHERE clave = ? AND activa = 1', [mb_strtolower($clave)]);
}

function dependencia_id(int $id): ?array
{
    return fila_una('SELECT * FROM dependencias WHERE id = ?', [$id]);
}

function dependencias(): array
{
    return filas('SELECT * FROM dependencias ORDER BY clave');
}

function horarios(int $dependencia): array
{
    return filas('SELECT * FROM horarios WHERE dependencia_id = ? ORDER BY dia, inicio', [$dependencia]);
}

function excepciones(int $dependencia, string $desde, string $hasta): array
{
    return filas('SELECT * FROM excepciones WHERE dependencia_id = ? AND fecha BETWEEN ? AND ? ORDER BY fecha',
        [$dependencia, $desde, $hasta]);
}

function bloqueos(int $dependencia, DateTimeImmutable $dia): array
{
    $crudos = filas(
        'SELECT * FROM bloqueos WHERE dependencia_id = ? AND inicio < ? AND fin > ? ORDER BY inicio',
        [$dependencia, $dia->setTime(23, 59, 59)->format('Y-m-d H:i:s'),
         $dia->setTime(0, 0, 0)->format('Y-m-d H:i:s')]
    );
    // array_merge y no '+': el operador conservaria las cadenas originales.
    return array_map(
        fn($b) => array_merge($b, ['inicio' => a_momento($b['inicio']), 'fin' => a_momento($b['fin'])]),
        $crudos
    );
}

function turnos_del_dia(int $dependencia, string $fecha): array
{
    return filas('SELECT * FROM turnos WHERE dependencia_id = ? AND fecha = ? ORDER BY folio', [$dependencia, $fecha]);
}

/**
 * Estado completo de la fila con las horas estimadas ya calculadas.
 * Es la unica fuente de verdad: la usan la pagina publica, la pantalla y la laptop.
 */
function fila_estado(array $dep, ?DateTimeImmutable $ahora = null): array
{
    $ahora = $ahora ?? new DateTimeImmutable('now');
    $dia = $ahora->setTime(0, 0, 0);
    $fecha = $ahora->format('Y-m-d');

    $ventanas = Agenda::ventanas($dia, horarios((int) $dep['id']),
        excepciones((int) $dep['id'], $fecha, $fecha));
    $reuniones = bloqueos((int) $dep['id'], $dia);
    $turnos = turnos_del_dia((int) $dep['id'], $fecha);

    $entrada = array_map(fn($t) => [
        'id' => (int) $t['id'],
        'minutos' => (int) $t['minutos'],
        'estado' => $t['estado'],
        'llamado' => a_momento($t['llamado']),
    ], $turnos);

    $calculo = Agenda::calcular($ahora, $ventanas, $reuniones, $entrada, [
        'colchon_turno' => (int) $dep['colchon_turno'],
        'colchon_reunion' => (int) $dep['colchon_reunion'],
    ]);

    $actual = null;
    $lista = [];
    foreach ($turnos as $turno) {
        $turno['estimado_guardado'] = $turno['estimado'];   // el de la vuelta anterior
        $turno['estimado'] = $calculo['estimados'][(int) $turno['id']] ?? null;
        $turno['espera'] = Agenda::espera($ahora, $turno['estimado']);
        if ($turno['estado'] === 'llamado') {
            $actual = $turno;
        }
        $lista[] = $turno;
    }

    $siguiente = Agenda::acomodar($calculo['libre'], (int) $dep['duracion_max'], $ventanas, $reuniones,
        (int) $dep['colchon_reunion']);
    $abierta = ((int) $dep['disponible'] === 1) && $siguiente !== null;

    return [
        'dependencia' => $dep,
        'ahora' => $ahora,
        'ventanas' => $ventanas,
        'bloqueos' => $reuniones,
        'turnos' => $lista,
        'actual' => $actual,
        'espera' => array_values(array_filter($lista, fn($t) => $t['estado'] === 'espera')),
        'proximo_hueco' => $siguiente,
        'abierta' => $abierta,
        'motivo_cierre' => $abierta ? '' : (((int) $dep['disponible'] === 1)
            ? 'Por hoy ya no alcanza el horario de atención.'
            : ($dep['mensaje'] ?: 'En este momento no hay atención.')),
    ];
}

function turno_por_token(string $token): ?array
{
    return fila_una('SELECT * FROM turnos WHERE token = ?', [$token]);
}

function crear_turno(array $dep, string $nombre, string $email, string $asunto, int $minutos): array
{
    $fecha = (new DateTimeImmutable('now'))->format('Y-m-d');
    $token = u_token();
    for ($intento = 0; $intento < 5; $intento++) {
        $folio = (int) (fila_una('SELECT COALESCE(MAX(folio), 0) + 1 AS siguiente FROM turnos '
            . 'WHERE dependencia_id = ? AND fecha = ?', [$dep['id'], $fecha])['siguiente'] ?? 1);
        try {
            consulta('INSERT INTO turnos (dependencia_id, fecha, folio, nombre, nombre_publico, email, '
                . 'asunto, minutos, estado, token, creado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                [$dep['id'], $fecha, $folio, $nombre, u_nombre_corto($nombre), $email, $asunto,
                 $minutos, 'espera', $token, ahora_texto()]);
            evento((int) $dep['id'], 'turno', "folio {$folio} · {$email}");
            return turno_por_token($token);
        } catch (PDOException $error) {
            if ($intento === 4) {
                throw $error;   // dos personas tomaron turno en el mismo instante
            }
            usleep(50000);
        }
    }
    throw new RuntimeException('No se pudo crear el turno.');
}

function cancelar_turno(array $turno, string $quien = 'persona'): void
{
    consulta('UPDATE turnos SET estado = ?, cerrado = ? WHERE id = ? AND estado IN (?, ?)',
        ['cancelado', ahora_texto(), $turno['id'], 'espera', 'llamado']);
    evento((int) $turno['dependencia_id'], 'cancelacion', "folio {$turno['folio']} · {$quien}");
}

function turnos_activos_de(int $dependencia, string $email): array
{
    return filas('SELECT * FROM turnos WHERE dependencia_id = ? AND fecha = ? AND email = ? '
        . 'AND estado IN (?, ?)',
        [$dependencia, (new DateTimeImmutable('now'))->format('Y-m-d'), u_email($email), 'espera', 'llamado']);
}

// --- citas ---------------------------------------------------------------

function crear_cita(array $dep, string $nombre, string $email, string $asunto, string $descripcion,
                    int $minutos, string $propuesta): array
{
    $token = u_token();
    consulta('INSERT INTO citas (dependencia_id, nombre, email, asunto, descripcion, minutos, '
        . 'propuesta, estado, token, creado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [$dep['id'], $nombre, $email, $asunto, $descripcion, $minutos, $propuesta, 'solicitada',
         $token, ahora_texto()]);
    evento((int) $dep['id'], 'cita', "{$email} · {$propuesta}");
    return cita_por_token($token);
}

function cita_por_token(string $token): ?array
{
    return fila_una('SELECT * FROM citas WHERE token = ?', [$token]);
}

function citas(int $dependencia, string $estado = 'solicitada'): array
{
    return filas('SELECT * FROM citas WHERE dependencia_id = ? AND estado = ? ORDER BY propuesta',
        [$dependencia, $estado]);
}

function adjuntos_de(int $cita): array
{
    return filas('SELECT * FROM adjuntos WHERE cita_id = ? ORDER BY id', [$cita]);
}

/** Aprueba la cita y reserva su bloque para que la fila lo respete. */
function aprobar_cita(array $cita, ?string $inicio = null, string $motivo = ''): array
{
    $inicio = $inicio ?: $cita['propuesta'];
    $arranque = a_momento($inicio);
    $fin = $arranque->modify('+' . (int) $cita['minutos'] . ' minutes');

    consulta('UPDATE citas SET estado = ?, confirmada = ?, motivo = ?, resuelta = ? WHERE id = ?',
        ['aprobada', $arranque->format('Y-m-d H:i:s'), $motivo, ahora_texto(), $cita['id']]);
    consulta('DELETE FROM bloqueos WHERE cita_id = ?', [$cita['id']]);
    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen, cita_id) '
        . 'VALUES (?, ?, ?, ?, ?, ?)',
        [$cita['dependencia_id'], $arranque->format('Y-m-d H:i:s'), $fin->format('Y-m-d H:i:s'),
         mb_substr('Cita: ' . $cita['asunto'], 0, 160), 'cita', $cita['id']]);
    evento((int) $cita['dependencia_id'], 'cita-aprobada', $cita['email']);
    return cita_por_token($cita['token']);
}

function rechazar_cita(array $cita, string $motivo): array
{
    consulta('UPDATE citas SET estado = ?, motivo = ?, resuelta = ? WHERE id = ?',
        ['rechazada', mb_substr($motivo, 0, 255), ahora_texto(), $cita['id']]);
    consulta('DELETE FROM bloqueos WHERE cita_id = ?', [$cita['id']]);
    evento((int) $cita['dependencia_id'], 'cita-rechazada', $cita['email']);
    return cita_por_token($cita['token']);
}

function cancelar_cita(array $cita, string $quien = 'persona'): void
{
    consulta('UPDATE citas SET estado = ?, resuelta = ? WHERE id = ?',
        ['cancelada', ahora_texto(), $cita['id']]);
    consulta('DELETE FROM bloqueos WHERE cita_id = ?', [$cita['id']]);
    evento((int) $cita['dependencia_id'], 'cita-cancelada', "{$cita['email']} · {$quien}");
}

// --- verificacion por correo --------------------------------------------

function verificacion_crear(array $dep, string $email, array $carga): array
{
    $codigo = u_codigo();
    $expira = (new DateTimeImmutable('now'))->modify('+20 minutes');
    consulta('INSERT INTO verificaciones (dependencia_id, email, codigo_hash, carga, expira, ip, creado) '
        . 'VALUES (?, ?, ?, ?, ?, ?, ?)',
        [$dep['id'], $email, hash('sha256', $codigo), json_encode($carga, JSON_UNESCAPED_UNICODE),
         $expira->format('Y-m-d H:i:s'), u_ip(), ahora_texto()]);
    return ['codigo' => $codigo, 'id' => (int) db()->lastInsertId()];
}

function verificacion_comprobar(array $dep, string $email, string $codigo): ?array
{
    $registro = fila_una('SELECT * FROM verificaciones WHERE dependencia_id = ? AND email = ? '
        . 'AND usado IS NULL AND expira > ? ORDER BY id DESC LIMIT 1',
        [$dep['id'], u_email($email), ahora_texto()]);
    if ($registro === null || (int) $registro['intentos'] >= 5) {
        return null;
    }
    consulta('UPDATE verificaciones SET intentos = intentos + 1 WHERE id = ?', [$registro['id']]);
    if (!hash_equals($registro['codigo_hash'], hash('sha256', trim($codigo)))) {
        return null;
    }
    consulta('UPDATE verificaciones SET usado = ? WHERE id = ?', [ahora_texto(), $registro['id']]);
    $carga = json_decode((string) $registro['carga'], true);
    return is_array($carga) ? $carga : null;
}

/** Freno sencillo contra abuso del QR publico. */
function demasiadas_solicitudes(string $email, string $ip): bool
{
    $desde = (new DateTimeImmutable('now'))->modify('-1 hour')->format('Y-m-d H:i:s');
    $porCorreo = (int) (fila_una('SELECT COUNT(*) AS n FROM verificaciones WHERE email = ? AND creado > ?',
        [u_email($email), $desde])['n'] ?? 0);
    $porIp = (int) (fila_una('SELECT COUNT(*) AS n FROM verificaciones WHERE ip = ? AND creado > ?',
        [$ip, $desde])['n'] ?? 0);
    return $porCorreo >= 5 || $porIp >= 15;
}

function evento(?int $dependencia, string $accion, string $detalle = ''): void
{
    consulta('INSERT INTO eventos (dependencia_id, momento, accion, detalle) VALUES (?, ?, ?, ?)',
        [$dependencia, ahora_texto(), $accion, mb_substr($detalle, 0, 255)]);
}

/**
 * Horas libres para agendar una reunion de `minutos`, agrupadas por dia.
 * Descuenta reuniones ya confirmadas y solicitudes aun sin resolver, para que
 * dos personas no propongan el mismo hueco.
 */
function huecos(array $dep, int $minutos, int $dias = 10, int $porDia = 6): array
{
    $ahora = new DateTimeImmutable('now');
    $desde = $ahora->modify('+60 minutes');       // nadie agenda para dentro de un minuto
    $pendientes = filas('SELECT propuesta, minutos FROM citas WHERE dependencia_id = ? AND estado = ? '
        . 'AND propuesta > ?', [$dep['id'], 'solicitada', $ahora->format('Y-m-d H:i:s')]);

    $resultado = [];
    for ($salto = 0; $salto <= $dias && count($resultado) < 6; $salto++) {
        $dia = $ahora->modify("+{$salto} days")->setTime(0, 0, 0);
        $fecha = $dia->format('Y-m-d');
        $ventanas = Agenda::ventanas($dia, horarios((int) $dep['id']),
            excepciones((int) $dep['id'], $fecha, $fecha));
        if (!$ventanas) {
            continue;
        }
        $ocupado = bloqueos((int) $dep['id'], $dia);
        foreach ($pendientes as $cita) {
            $inicio = a_momento($cita['propuesta']);
            if ($inicio && $inicio->format('Y-m-d') === $fecha) {
                $ocupado[] = ['inicio' => $inicio,
                              'fin' => $inicio->modify('+' . (int) $cita['minutos'] . ' minutes')];
            }
        }

        $cursor = $salto === 0 ? $desde : $dia;
        $opciones = [];
        while (count($opciones) < $porDia) {
            $hueco = Agenda::acomodar($cursor, $minutos, $ventanas, $ocupado,
                (int) $dep['colchon_reunion']);
            if ($hueco === null || $hueco->format('Y-m-d') !== $fecha) {
                break;
            }
            $opciones[] = $hueco;
            $cursor = $hueco->modify('+' . ($minutos + (int) $dep['colchon_turno']) . ' minutes');
        }
        if ($opciones) {
            $resultado[] = ['dia' => $dia, 'opciones' => $opciones];
        }
    }
    return $resultado;
}

/** Minutos permitidos para una reunion agendada, segun la dependencia. */
function minutos_de_cita(array $dep): array
{
    $valores = array_map('intval', array_filter(explode(',', (string) $dep['minutos_cita'])));
    return $valores ?: [20, 30, 45];
}
