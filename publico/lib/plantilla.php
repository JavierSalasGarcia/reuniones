<?php
declare(strict_types=1);

require_once __DIR__ . '/util.php';

function base_url(): string
{
    return rtrim((string) (config()['base_url'] ?? '/citas'), '/');
}

function ruta(string $destino = ''): string
{
    return base_url() . ($destino ? '/' . ltrim($destino, '/') : '');
}

function csrf(): string
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = u_token(16);
    }
    return $_SESSION['csrf'];
}

function csrf_valido(): bool
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
    $enviado = (string) ($_POST['csrf'] ?? '');
    return $enviado !== '' && hash_equals((string) ($_SESSION['csrf'] ?? ''), $enviado);
}

function campo_csrf(): string
{
    return '<input type="hidden" name="csrf" value="' . u_escapar(csrf()) . '">';
}

function render(string $vista, array $datos = [], array $opciones = []): void
{
    $contenido = parcial($vista, $datos);
    $titulo = $opciones['titulo'] ?? 'Citas';
    $dep = $datos['dep'] ?? null;
    $desnudo = !empty($opciones['desnudo']);   // la pantalla del monitor va sin barra
    include __DIR__ . '/../vistas/base.php';
}

function parcial(string $vista, array $datos = []): string
{
    extract($datos, EXTR_SKIP);
    ob_start();
    include __DIR__ . '/../vistas/' . $vista . '.php';
    return (string) ob_get_clean();
}
