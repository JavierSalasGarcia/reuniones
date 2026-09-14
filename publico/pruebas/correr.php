<?php
declare(strict_types=1);

/**
 * Corredor de pruebas sin dependencias:  php publico/pruebas/correr.php
 */
final class Pruebas
{
    public static int $ok = 0;
    /** @var string[] */
    public static array $fallas = [];
    public static string $actual = '';

    public static function caso(string $nombre, callable $cuerpo): void
    {
        self::$actual = $nombre;
        try {
            $cuerpo();
        } catch (Throwable $error) {
            self::$fallas[] = "{$nombre}: excepcion " . $error->getMessage();
        }
    }

    public static function igual($esperado, $obtenido, string $detalle = ''): void
    {
        $esperado = self::texto($esperado);
        $obtenido = self::texto($obtenido);
        if ($esperado === $obtenido) {
            self::$ok++;
            return;
        }
        self::$fallas[] = sprintf("%s%s: esperaba %s y obtuve %s",
            self::$actual, $detalle ? " ({$detalle})" : '', $esperado, $obtenido);
    }

    public static function cierto($valor, string $detalle = ''): void
    {
        self::igual(true, (bool) $valor, $detalle);
    }

    private static function texto($valor): string
    {
        if ($valor instanceof DateTimeInterface) {
            return $valor->format('Y-m-d H:i');
        }
        if (is_array($valor)) {
            return '[' . implode(', ', array_map([self::class, 'texto'], $valor)) . ']';
        }
        if (is_bool($valor)) {
            return $valor ? 'true' : 'false';
        }
        if ($valor === null) {
            return 'null';
        }
        if (is_string($valor)) {
            return $valor;
        }
        return var_export($valor, true);
    }

    public static function resumen(): int
    {
        if (self::$fallas) {
            echo "\n" . count(self::$fallas) . " falla(s):\n";
            foreach (self::$fallas as $falla) {
                echo "  - {$falla}\n";
            }
            return 1;
        }
        echo self::$ok . " comprobaciones correctas.\n";
        return 0;
    }
}

require __DIR__ . '/../lib/agenda.php';
require __DIR__ . '/../lib/util.php';
require __DIR__ . '/../lib/db.php';
require __DIR__ . '/agenda_prueba.php';
require __DIR__ . '/util_prueba.php';
require __DIR__ . '/flujo_prueba.php';
require __DIR__ . '/minutas_prueba.php';
require __DIR__ . '/jornada_prueba.php';

exit(Pruebas::resumen());
