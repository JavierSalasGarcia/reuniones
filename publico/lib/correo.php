<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/util.php';
require_once __DIR__ . '/datos.php';

/**
 * Correo del sistema: codigos de verificacion, avisos de la fila y minutas.
 *
 * Todo sale por el buzon de fingenieria.mx, porque el servidor de correo
 * institucional rechaza lo que no venga de un dominio autorizado. Modos:
 * smtp (el de produccion), mail o bitacora, que solo guarda los mensajes y
 * sirve para las pruebas.
 */

$GLOBALS['_correos_enviados'] = [];

/**
 * @param array $adjuntos  [['nombre' => ..., 'ruta' => ..., 'tipo' => ...], ...]
 */
function correo_enviar(string $para, string $asunto, string $cuerpo, array $adjuntos = []): bool
{
    $cfg = config()['correo'] ?? [];
    $modo = $cfg['modo'] ?? 'smtp';
    $remitente = $cfg['remitente'] ?? ('no-responder@' . ($_SERVER['HTTP_HOST'] ?? 'localhost'));
    $nombre = $cfg['remitente_nombre'] ?? 'Agenda';

    $GLOBALS['_correos_enviados'][] = [
        'para' => $para, 'asunto' => $asunto, 'cuerpo' => $cuerpo,
        'adjuntos' => array_map(fn($a) => $a['nombre'] ?? '', $adjuntos),
    ];
    if ($modo === 'bitacora') {
        return true;
    }

    $armado = correo_armar($cuerpo, $adjuntos);
    $cabeceras = [
        'From: ' . correo_direccion($nombre, $remitente),
        'Reply-To: ' . ($cfg['responder_a'] ?: $remitente),
        'MIME-Version: 1.0',
        'Content-Type: ' . $armado['tipo'],
    ];

    if ($modo === 'smtp') {
        return correo_smtp($para, $asunto, $armado, $cfg, $remitente, $nombre);
    }
    return @mail($para, correo_asunto($asunto), $armado['cuerpo'], implode("\r\n", $cabeceras));
}

function correo_direccion(string $nombre, string $correo): string
{
    return sprintf('=?UTF-8?B?%s?= <%s>', base64_encode($nombre), $correo);
}

function correo_asunto(string $asunto): string
{
    return '=?UTF-8?B?' . base64_encode($asunto) . '?=';
}

/** Arma el cuerpo MIME: texto solo, o multipart cuando lleva adjuntos. */
function correo_armar(string $texto, array $adjuntos = []): array
{
    $adjuntos = array_values(array_filter($adjuntos, fn($a) => is_file($a['ruta'] ?? '')));
    if (!$adjuntos) {
        return ['tipo' => 'text/plain; charset=UTF-8', 'cuerpo' => $texto];
    }

    $frontera = 'lim' . bin2hex(random_bytes(12));
    $partes = ["--{$frontera}", 'Content-Type: text/plain; charset=UTF-8',
               'Content-Transfer-Encoding: 8bit', '', $texto, ''];
    foreach ($adjuntos as $adjunto) {
        $nombre = basename((string) ($adjunto['nombre'] ?? $adjunto['ruta']));
        $partes[] = "--{$frontera}";
        $partes[] = 'Content-Type: ' . ($adjunto['tipo'] ?? 'application/octet-stream')
            . '; name="' . $nombre . '"';
        $partes[] = 'Content-Transfer-Encoding: base64';
        $partes[] = 'Content-Disposition: attachment; filename="' . $nombre . '"';
        $partes[] = '';
        $partes[] = trim(chunk_split(base64_encode((string) file_get_contents($adjunto['ruta'])), 76, "\r\n"));
        $partes[] = '';
    }
    $partes[] = "--{$frontera}--";

    return [
        'tipo' => "multipart/mixed; boundary=\"{$frontera}\"",
        'cuerpo' => implode("\r\n", $partes),
    ];
}

function correo_smtp(string $para, string $asunto, array $armado, array $cfg,
                     string $remitente, string $nombre): bool
{
    $servidor = $cfg['servidor'] ?? '';
    $puerto = (int) ($cfg['puerto'] ?? 587);
    $destino = ($puerto === 465 ? 'ssl://' : '') . $servidor . ':' . $puerto;
    $conexion = @stream_socket_client($destino, $codigo, $error, 20);
    if (!$conexion) {
        error_log("SMTP sin conexion: {$error}");
        return false;
    }
    stream_set_timeout($conexion, 20);

    $leer = function () use ($conexion): string {
        $respuesta = '';
        while ($linea = fgets($conexion, 515)) {
            $respuesta .= $linea;
            if (strlen($linea) < 4 || $linea[3] === ' ') {
                break;
            }
        }
        return $respuesta;
    };
    $decir = function (string $orden) use ($conexion, $leer): string {
        fwrite($conexion, $orden . "\r\n");
        return $leer();
    };

    $saludo = $cfg['saludo'] ?? ($_SERVER['HTTP_HOST'] ?? 'localhost');
    $leer();
    $decir('EHLO ' . $saludo);
    if ($puerto !== 465) {
        $decir('STARTTLS');
        if (!stream_socket_enable_crypto($conexion, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) {
            fclose($conexion);
            error_log('SMTP: no se pudo cifrar la conexion');
            return false;
        }
        $decir('EHLO ' . $saludo);
    }
    if (!empty($cfg['usuario'])) {
        $decir('AUTH LOGIN');
        $decir(base64_encode((string) $cfg['usuario']));
        $respuestaClave = $decir(base64_encode((string) ($cfg['clave'] ?? '')));
        if (!str_starts_with(trim($respuestaClave), '235')) {
            $decir('QUIT');
            fclose($conexion);
            error_log('SMTP: usuario o contrasena rechazados');
            return false;
        }
    }
    $decir('MAIL FROM:<' . $remitente . '>');
    $decir('RCPT TO:<' . $para . '>');
    $decir('DATA');

    $encabezado = "From: " . correo_direccion($nombre, $remitente) . "\r\n"
        . "To: <{$para}>\r\n"
        . 'Reply-To: ' . ($cfg['responder_a'] ?: $remitente) . "\r\n"
        . 'Subject: ' . correo_asunto($asunto) . "\r\n"
        . "MIME-Version: 1.0\r\n"
        . 'Content-Type: ' . $armado['tipo'] . "\r\n\r\n";
    // Una linea que empieza con punto se escapa: asi lo pide el protocolo.
    $cuerpo = preg_replace('/^\./m', '..', $armado['cuerpo']);
    $respuesta = $decir($encabezado . $cuerpo . "\r\n.");
    $decir('QUIT');
    fclose($conexion);
    return str_starts_with(trim($respuesta), '250');
}

// --- mensajes ------------------------------------------------------------

function correo_codigo(array $dep, string $para, string $codigo): void
{
    correo_enviar($para, "Código para tu turno · {$dep['nombre']}",
        "Tu código de confirmación es {$codigo}\n\n"
        . "Escríbelo en la página para confirmar tu turno o tu solicitud de cita. "
        . "Vence en 20 minutos.\n\nSi no fuiste tú, ignora este mensaje.");
}

function correo_turno(array $dep, array $turno, ?DateTimeImmutable $estimado, string $enlace): void
{
    $hora = $estimado ? u_hora($estimado) : 'por definir';
    correo_enviar($turno['email'], "Turno {$turno['folio']} · {$dep['nombre']}",
        "Tomaste el turno {$turno['folio']} con {$dep['titular']}.\n\n"
        . "Hora aproximada de atención: {$hora}\n"
        . "Asunto: {$turno['asunto']}\n\n"
        . "Puedes ver cómo avanza la fila y cancelar tu turno aquí:\n{$enlace}\n\n"
        . "Si no vas a poder llegar, cancela para no retrasar a quienes siguen.");
}

function correo_recorrido(array $dep, array $turno, ?DateTimeImmutable $estimado, string $enlace): void
{
    $hora = $estimado ? u_hora($estimado) : 'sin hora por hoy';
    correo_enviar($turno['email'], "Tu turno {$turno['folio']} se recorrió · {$dep['nombre']}",
        "La fila se movió y tu turno quedó para las {$hora} aproximadamente.\n\n"
        . "Si a esa hora ya no puedes, cancélalo aquí:\n{$enlace}");
}

function correo_cita_solicitada(array $dep, array $cita, string $enlace): void
{
    correo_enviar($cita['email'], "Solicitud de reunión recibida · {$dep['nombre']}",
        "Recibimos tu solicitud de reunión con {$dep['titular']}.\n\n"
        . 'Fecha propuesta: ' . u_fecha_larga(a_momento($cita['propuesta'])) . "\n"
        . "Asunto: {$cita['asunto']}\n\n"
        . "Queda pendiente de confirmación. Te avisaremos por este medio.\n"
        . "Puedes consultarla o cancelarla aquí:\n{$enlace}");
}

function correo_cita_resuelta(array $dep, array $cita, string $enlace): void
{
    if ($cita['estado'] === 'aprobada') {
        $cuando = u_fecha_larga(a_momento($cita['confirmada'] ?: $cita['propuesta']));
        correo_enviar($cita['email'], "Reunión confirmada · {$dep['nombre']}",
            "Tu reunión con {$dep['titular']} quedó confirmada para el {$cuando}.\n\n"
            . "Asunto: {$cita['asunto']}\n"
            . "Duración prevista: {$cita['minutos']} minutos.\n\n"
            . "Si necesitas cancelarla:\n{$enlace}");
        return;
    }
    $motivo = $cita['motivo'] ? "\n\nMotivo: {$cita['motivo']}" : '';
    correo_enviar($cita['email'], "Solicitud de reunión no confirmada · {$dep['nombre']}",
        "Tu solicitud de reunión con {$dep['titular']} no pudo confirmarse en la fecha propuesta."
        . $motivo . "\n\nPuedes proponer otra fecha desde la página de la dependencia.");
}

/** Manda la minuta en PDF desde el servidor, con copia guardada en el expediente. */
function correo_minuta(array $dep, array $minuta, string $destinatario, string $mensaje = ''): bool
{
    $ruta = ruta_subida((string) $minuta['archivo']);
    if (!is_file($ruta)) {
        return false;
    }
    $fecha = a_momento((string) $minuta['fecha']);
    $titulo = 'Minuta de reunión' . ($fecha ? ' · ' . $fecha->format('d/m/Y') : '');
    if ($minuta['asunto']) {
        $titulo .= ' · ' . mb_substr((string) $minuta['asunto'], 0, 60);
    }
    $nombre = trim((string) $minuta['persona']);
    $primero = $nombre ? explode(' ', $nombre)[0] : '';

    $cuerpo = trim($mensaje) ?: "Estimada o estimado {$primero}:\n\n"
        . 'Adjunto la minuta de nuestra reunión'
        . ($fecha ? ' del ' . u_fecha_larga($fecha) : '')
        . ($minuta['asunto'] ? ", sobre «{$minuta['asunto']}»" : '')
        . ", para que quede como antecedente de lo tratado y de los acuerdos alcanzados.\n\n"
        . "Si encuentra alguna imprecisión, le agradeceré que me lo haga saber.\n\n"
        . "Saludos cordiales,\n{$dep['titular']}\n{$dep['nombre']}";

    return correo_enviar($destinatario, $titulo, $cuerpo, [[
        'nombre' => $minuta['nombre'],
        'ruta' => $ruta,
        'tipo' => 'application/pdf',
    ]]);
}

/** Aviso a quien estaba formado cuando hay que cancelar la cola. */
function correo_cola_cancelada(array $dep, array $turno, string $motivo, string $enlace): void
{
    $razon = trim($motivo) !== '' ? "\n\nMotivo: {$motivo}" : '';
    correo_enviar($turno['email'], "Se canceló la atención de hoy · {$dep['nombre']}",
        "Lamentamos avisarte que tu turno {$turno['folio']} no podrá ser atendido hoy, "
        . "por causas ajenas a ti." . $razon . "\n\n"
        . "Puedes formarte mañana desde la misma página, o solicitar una reunión con fecha "
        . "y hora para no tener que esperar:\n{$enlace}\n\n"
        . "Una disculpa por el contratiempo.\n{$dep['titular']}");
}

/** Aviso de cancelacion de una cita ya confirmada, con enlace para reagendar. */
function correo_cita_cancelada(array $dep, array $cita, string $motivo, string $enlace): void
{
    $cuando = u_fecha_larga(a_momento($cita['confirmada'] ?: $cita['propuesta']));
    $razon = trim($motivo) !== '' ? "\n\nMotivo: {$motivo}" : '';
    correo_enviar($cita['email'], "Se canceló tu reunión · {$dep['nombre']}",
        "Tu reunión con {$dep['titular']} del {$cuando} tuvo que cancelarse." . $razon . "\n\n"
        . "Puedes elegir otra fecha aquí, sin volver a empezar el trámite:\n{$enlace}\n\n"
        . "Una disculpa por el cambio.\n{$dep['titular']}");
}
