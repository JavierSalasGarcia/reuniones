<?php
declare(strict_types=1);

/** Utilerias sueltas de la parte publica. */

function u_token(int $bytes = 16): string
{
    return bin2hex(random_bytes($bytes));
}

function u_codigo(): string
{
    return str_pad((string) random_int(0, 999999), 6, '0', STR_PAD_LEFT);
}

function u_limpio(?string $texto, int $largo = 200): string
{
    $limpio = trim(preg_replace('/\s+/u', ' ', strip_tags((string) $texto)) ?? '');
    return mb_substr($limpio, 0, $largo);
}

function u_texto_largo(?string $texto, int $largo = 4000): string
{
    $limpio = trim(strip_tags((string) $texto));
    return mb_substr($limpio, 0, $largo);
}

function u_email(?string $email): string
{
    return mb_strtolower(trim((string) $email));
}

function u_email_valido(string $email, string $dominio): bool
{
    $email = u_email($email);
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        return false;
    }
    $dominio = mb_strtolower(ltrim(trim($dominio), '@'));
    if ($dominio === '') {
        return true;
    }
    $suyo = substr($email, strrpos($email, '@') + 1);
    return $suyo === $dominio || str_ends_with($suyo, '.' . $dominio);
}

/** Nombre y primer apellido: lo que se muestra en la pantalla publica. */
function u_nombre_corto(string $nombre): string
{
    $partes = preg_split('/\s+/u', trim($nombre)) ?: [];
    $partes = array_values(array_filter($partes, fn($p) => $p !== ''));
    if (count($partes) <= 2) {
        return implode(' ', $partes);
    }
    return $partes[0] . ' ' . $partes[1];
}

function u_sin_acentos(string $texto): string
{
    return iconv('UTF-8', 'ASCII//TRANSLIT', $texto) ?: $texto;
}

function u_escapar(?string $texto): string
{
    return htmlspecialchars((string) $texto, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function u_hora(?DateTimeInterface $momento): string
{
    return $momento ? $momento->format('H:i') : '';
}

function u_fecha_larga(?DateTimeInterface $momento): string
{
    if (!$momento) {
        return '';
    }
    $dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
    $meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
              'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    return sprintf('%s %d de %s, %s',
        $dias[(int) $momento->format('N') - 1],
        (int) $momento->format('j'),
        $meses[(int) $momento->format('n') - 1],
        $momento->format('H:i'));
}

/** "en 25 minutos", "en una hora y cuarto", "ahora". */
function u_espera_en_palabras(?int $minutos): string
{
    if ($minutos === null) {
        return 'sin hora todavía';
    }
    if ($minutos <= 1) {
        return 'ahora';
    }
    if ($minutos < 60) {
        return "en unos {$minutos} minutos";
    }
    $horas = intdiv($minutos, 60);
    $resto = $minutos % 60;
    $texto = $horas === 1 ? 'en una hora' : "en {$horas} horas";
    if ($resto >= 10) {
        $texto .= " y {$resto} minutos";
    }
    return $texto;
}

function u_ip(): string
{
    return (string) ($_SERVER['REMOTE_ADDR'] ?? '');
}

function u_json($datos, int $codigo = 200): void
{
    http_response_code($codigo);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($datos, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}

function u_redirigir(string $destino): void
{
    header('Location: ' . $destino);
    exit;
}

/** Nombre seguro para carpetas y archivos. */
function u_apodo(string $texto, int $largo = 60): string
{
    $sin = iconv('UTF-8', 'ASCII//TRANSLIT', $texto) ?: $texto;
    $limpio = strtolower(trim(preg_replace('/[^A-Za-z0-9]+/', '-', $sin) ?? '', '-'));
    return mb_substr($limpio, 0, $largo) ?: 'sin-nombre';
}
