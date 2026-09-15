<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/util.php';

/**
 * Aviso inmediato al celular del titular, que el reloj repite vibrando.
 *
 * Usa ntfy: el servidor publica en un tema y la app del celular, suscrita a
 * ese tema, muestra la notificacion. El tema es una cadena larga al azar que
 * funciona como contrasena, porque quien la conozca puede leer los avisos.
 */

$GLOBALS['_push_enviados'] = [];

function push_modo(): string
{
    return (string) ((config()['push'] ?? [])['modo'] ?? 'off');
}

function push_configurado(array $dep): bool
{
    return push_modo() !== 'off' && trim((string) ($dep['push_tema'] ?? '')) !== '';
}

function push_enviar(array $dep, string $titulo, string $mensaje, array $opciones = []): bool
{
    if (!push_configurado($dep)) {
        return false;
    }
    $cfg = config()['push'] ?? [];
    $tema = trim((string) $dep['push_tema']);

    $GLOBALS['_push_enviados'][] = [
        'tema' => $tema, 'titulo' => $titulo, 'mensaje' => $mensaje,
    ] + $opciones;

    if (push_modo() === 'bitacora') {
        return true;
    }

    $cabeceras = [
        'Title: ' . push_cabecera($titulo),
        'Priority: ' . (string) ($opciones['prioridad'] ?? 'default'),
        'Tags: ' . (string) ($opciones['etiquetas'] ?? 'bell'),
    ];
    if (!empty($opciones['abrir'])) {
        $cabeceras[] = 'Click: ' . $opciones['abrir'];
    }
    if (!empty($cfg['token'])) {
        $cabeceras[] = 'Authorization: Bearer ' . $cfg['token'];
    }

    $curl = curl_init(rtrim((string) ($cfg['servidor'] ?? 'https://ntfy.sh'), '/') . '/' . $tema);
    curl_setopt_array($curl, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $mensaje,
        CURLOPT_HTTPHEADER => $cabeceras,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 8,
    ]);
    $respuesta = curl_exec($curl);
    $codigo = (int) curl_getinfo($curl, CURLINFO_HTTP_CODE);
    curl_close($curl);

    if ($respuesta === false || $codigo >= 300) {
        error_log("push fallido ({$codigo}) para {$dep['clave']}");
        return false;
    }
    return true;
}

/** Las cabeceras HTTP no admiten acentos ni saltos de linea. */
function push_cabecera(string $texto): string
{
    $plano = str_replace(["\r", "\n"], ' ', u_sin_acentos($texto));
    return trim(preg_replace('/\s+/', ' ', $plano) ?? '');
}

/** Alguien acaba de formarse en la cola. */
function push_turno_nuevo(array $dep, array $turno, ?DateTimeImmutable $estimado = null): bool
{
    if (!push_activo($dep, 'formado')) {
        return false;
    }
    $folio = (int) $turno['folio'];
    $conDetalle = (int) ($dep['push_detalle'] ?? 1) === 1;
    $titulo = $conDetalle
        ? "Turno {$folio} · " . u_nombre_corto((string) $turno['nombre'])
        : "Nuevo turno {$folio}";

    $partes = [];
    if ($conDetalle && trim((string) $turno['asunto']) !== '') {
        $partes[] = (string) $turno['asunto'];
    }
    $partes[] = ((int) $turno['minutos']) . ' min';
    if ($estimado !== null) {
        $partes[] = 'le tocaría ' . u_hora($estimado);
    }

    return push_enviar($dep, $titulo, implode(' · ', $partes), [
        'etiquetas' => 'bust_in_silhouette',
        'abrir' => rtrim((string) (config()['sitio'] ?? ''), '/') . '/' . $dep['clave'] . '/fila',
    ]);
}

// --- avisos que dependen de la hora --------------------------------------
//
// Estos no los dispara nadie desde la pagina: se revisan cada vez que la
// laptop o el reloj consultan al servidor, que es a lo que llamamos latido.
// Las senales recuerdan lo ya avisado para no repetir la vibracion.

const MINUTOS_ANTES = 5;   // anticipacion del aviso de cita proxima

function push_activo(array $dep, string $aviso): bool
{
    $lista = array_map('trim', explode(',', (string) ($dep['push_avisos'] ?? 'formado,excedido,cita,vacia')));
    return in_array($aviso, $lista, true);
}

function senal(array $dep, string $clave): ?string
{
    $fila = fila_una('SELECT valor FROM senales WHERE dependencia_id = ? AND clave = ?',
        [$dep['id'], $clave]);
    return $fila === null ? null : (string) $fila['valor'];
}

function guardar_senal(array $dep, string $clave, string $valor): void
{
    consulta('DELETE FROM senales WHERE dependencia_id = ? AND clave = ?', [$dep['id'], $clave]);
    consulta('INSERT INTO senales (dependencia_id, clave, valor, momento) VALUES (?, ?, ?, ?)',
        [$dep['id'], $clave, mb_substr($valor, 0, 80), ahora_texto()]);
}

/** Devuelve true la primera vez que se pregunta por esa clave. */
function primera_vez(array $dep, string $clave): bool
{
    if (senal($dep, $clave) !== null) {
        return false;
    }
    guardar_senal($dep, $clave, '1');
    return true;
}

function limpiar_senales(array $dep, int $dias = 7): void
{
    consulta('DELETE FROM senales WHERE dependencia_id = ? AND momento < ?',
        [$dep['id'], (new DateTimeImmutable('now'))->modify("-{$dias} days")->format('Y-m-d H:i:s')]);
}

/**
 * Revisa los tres avisos de reloj y manda los que toquen.
 * Devuelve las claves de los avisos enviados, para poder probarlo.
 */
function avisos_del_momento(array $dep, array $estado): array
{
    if (!push_configurado($dep)) {
        return [];
    }
    $enviados = [];
    $ahora = $estado['ahora'];
    $conDetalle = (int) ($dep['push_detalle'] ?? 1) === 1;

    // 1. La reunion en curso ya se paso del tiempo que la persona estimo.
    $actual = $estado['actual'] ?? null;
    if ($actual !== null && push_activo($dep, 'excedido')
        && (int) ($actual['restan'] ?? 0) < 0
        && primera_vez($dep, "excedido:{$actual['id']}")) {
        $quien = $conDetalle ? u_nombre_corto((string) $actual['nombre']) : "Turno {$actual['folio']}";
        push_enviar($dep, "Se pasó el tiempo · {$quien}",
            "Llevan {$actual['transcurridos']} de {$actual['minutos']} minutos",
            ['etiquetas' => 'hourglass', 'prioridad' => 'high']);
        $enviados[] = "excedido:{$actual['id']}";
    }

    // 2. Una reunion agendada esta por empezar.
    if (push_activo($dep, 'cita')) {
        $limite = $ahora->modify('+' . MINUTOS_ANTES . ' minutes');
        foreach ($estado['bloqueos'] as $bloqueo) {
            if ($bloqueo['inicio'] <= $ahora || $bloqueo['inicio'] > $limite) {
                continue;
            }
            if (!primera_vez($dep, "bloqueo:{$bloqueo['id']}")) {
                continue;
            }
            $detalle = (string) $bloqueo['motivo'];
            if ($bloqueo['cita_id']) {
                $cita = fila_una('SELECT nombre, asunto FROM citas WHERE id = ?', [$bloqueo['cita_id']]);
                if ($cita !== null) {
                    $detalle = $conDetalle
                        ? u_nombre_corto((string) $cita['nombre']) . ' · ' . $cita['asunto']
                        : 'Cita agendada';
                }
            }
            $faltan = max(1, (int) round(($bloqueo['inicio']->getTimestamp() - $ahora->getTimestamp()) / 60));
            push_enviar($dep, 'A las ' . u_hora($bloqueo['inicio']) . ", en {$faltan} min",
                $detalle, ['etiquetas' => 'calendar', 'prioridad' => 'high']);
            $enviados[] = "bloqueo:{$bloqueo['id']}";
        }
    }

    // 3. La cola se quedo vacia mientras sigues atendiendo.
    $esperando = count($estado['espera']);
    $previo = senal($dep, 'espera');
    guardar_senal($dep, 'espera', (string) $esperando);
    if (push_activo($dep, 'vacia') && $previo !== null && (int) $previo > 0 && $esperando === 0
        && in_array($estado['atencion'], ['atendiendo', 'ocupado'], true)) {
        push_enviar($dep, 'Cola vacía', 'Ya no hay nadie esperando',
            ['etiquetas' => 'white_check_mark']);
        $enviados[] = 'vacia';
    }

    limpiar_senales($dep);
    return $enviados;
}
