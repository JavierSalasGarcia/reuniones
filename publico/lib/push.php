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
