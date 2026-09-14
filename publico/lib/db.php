<?php
declare(strict_types=1);

/** Conexion PDO unica. En pruebas se inyecta con db_usar(). */

$GLOBALS['_pdo'] = null;
$GLOBALS['_config'] = null;

function config(): array
{
    if ($GLOBALS['_config'] === null) {
        $ruta = __DIR__ . '/../config.php';
        if (!is_file($ruta)) {
            http_response_code(500);
            exit('Falta config.php. Copia config.example.php y ajusta los datos.');
        }
        $GLOBALS['_config'] = require $ruta;
    }
    return $GLOBALS['_config'];
}

function config_usar(array $valores): void
{
    $GLOBALS['_config'] = $valores;
}

function db(): PDO
{
    if ($GLOBALS['_pdo'] instanceof PDO) {
        return $GLOBALS['_pdo'];
    }
    $cfg = config()['db'];
    $pdo = new PDO($cfg['dsn'], $cfg['usuario'] ?? '', $cfg['clave'] ?? '', [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    $GLOBALS['_pdo'] = $pdo;
    return $pdo;
}

function db_usar(PDO $pdo): void
{
    $GLOBALS['_pdo'] = $pdo;
}

function consulta(string $sql, array $parametros = []): PDOStatement
{
    $sentencia = db()->prepare($sql);
    $sentencia->execute($parametros);
    return $sentencia;
}

function fila_una(string $sql, array $parametros = []): ?array
{
    $fila = consulta($sql, $parametros)->fetch();
    return $fila === false ? null : $fila;
}

function filas(string $sql, array $parametros = []): array
{
    return consulta($sql, $parametros)->fetchAll();
}

function ahora_texto(): string
{
    return (new DateTimeImmutable('now'))->format('Y-m-d H:i:s');
}

function a_momento(?string $texto): ?DateTimeImmutable
{
    if ($texto === null || $texto === '') {
        return null;
    }
    try {
        return new DateTimeImmutable($texto);
    } catch (Exception $error) {
        return null;
    }
}
