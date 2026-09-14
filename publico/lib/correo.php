<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/util.php';

/**
 * Correos de la fila (codigo de verificacion, confirmaciones y avisos).
 *
 * Estos salen desde el buzon del hosting; la minuta se envia aparte desde la
 * laptop con la cuenta institucional. Modos: mail (por omision), smtp o
 * bitacora, que solo guarda los mensajes y sirve para pruebas.
 */

$GLOBALS['_correos_enviados'] = [];

function correo_enviar(string $para, string $asunto, string $cuerpo): bool
{
    $cfg = config()['correo'] ?? [];
    $modo = $cfg['modo'] ?? 'mail';
    $remitente = $cfg['remitente'] ?? ('no-responder@' . ($_SERVER['HTTP_HOST'] ?? 'localhost'));
    $nombre = $cfg['remitente_nombre'] ?? 'Agenda';

    $GLOBALS['_correos_enviados'][] = ['para' => $para, 'asunto' => $asunto, 'cuerpo' => $cuerpo];

    if ($modo === 'bitacora') {
        return true;
    }
    $cabeceras = [
        'From: ' . sprintf('%s <%s>', $nombre, $remitente),
        'Reply-To: ' . ($cfg['responder_a'] ?? $remitente),
        'Content-Type: text/plain; charset=UTF-8',
        'MIME-Version: 1.0',
    ];
    if ($modo === 'smtp') {
        return correo_smtp($para, $asunto, $cuerpo, $cfg, $remitente, $nombre);
    }
    return @mail($para, $asunto, $cuerpo, implode("\r\n", $cabeceras));
}

function correo_smtp(string $para, string $asunto, string $cuerpo, array $cfg,
                     string $remitente, string $nombre): bool
{
    $servidor = $cfg['servidor'] ?? '';
    $puerto = (int) ($cfg['puerto'] ?? 587);
    $destino = ($puerto === 465 ? 'ssl://' : '') . $servidor . ':' . $puerto;
    $conexion = @stream_socket_client($destino, $codigo, $error, 15);
    if (!$conexion) {
        error_log("SMTP sin conexion: {$error}");
        return false;
    }

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

    $leer();
    $decir('EHLO ' . ($_SERVER['HTTP_HOST'] ?? 'localhost'));
    if ($puerto !== 465) {
        $decir('STARTTLS');
        if (!stream_socket_enable_crypto($conexion, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) {
            fclose($conexion);
            return false;
        }
        $decir('EHLO ' . ($_SERVER['HTTP_HOST'] ?? 'localhost'));
    }
    if (!empty($cfg['usuario'])) {
        $decir('AUTH LOGIN');
        $decir(base64_encode((string) $cfg['usuario']));
        $decir(base64_encode((string) ($cfg['clave'] ?? '')));
    }
    $decir('MAIL FROM:<' . $remitente . '>');
    $decir('RCPT TO:<' . $para . '>');
    $decir('DATA');
    $mensaje = "From: {$nombre} <{$remitente}>\r\nTo: <{$para}>\r\n"
        . 'Subject: =?UTF-8?B?' . base64_encode($asunto) . "?=\r\n"
        . "MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n"
        . str_replace("\n.", "\n..", $cuerpo) . "\r\n.";
    $respuesta = $decir($mensaje);
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
