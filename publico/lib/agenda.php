<?php
declare(strict_types=1);

/**
 * Calculo de la fila: a que hora aproximada le toca a cada persona.
 *
 * Reglas:
 *  - Cada turno dura lo que la persona estimo, con un tope (10 minutos).
 *  - Entre turno y turno queda un colchon corto.
 *  - Antes de una reunion agendada queda un colchon mayor, y ningun turno
 *    puede invadirla: los que no alcanzan se recorren al terminar la reunion.
 *  - Los turnos solo caben dentro de los horarios de atencion del dia.
 *  - Lo que ya no alcanza hoy se marca como sin hora, y la fila se cierra.
 */
final class Agenda
{
    /** Intervalos de atencion del dia, ya ordenados y sin traslapes. */
    public static function ventanas(DateTimeImmutable $dia, array $horarios, array $excepciones = []): array
    {
        $fecha = $dia->format('Y-m-d');
        $delDia = array_values(array_filter($excepciones, fn($e) => ($e['fecha'] ?? '') === $fecha));

        foreach ($delDia as $excepcion) {
            if (($excepcion['tipo'] ?? 'cerrado') === 'cerrado' && empty($excepcion['inicio'])) {
                return [];   // dia cerrado completo
            }
        }

        $abiertas = array_values(array_filter($delDia, fn($e) => ($e['tipo'] ?? '') === 'abierto'));
        if ($abiertas) {
            $base = $abiertas;                       // el dia tiene horario especial
        } else {
            $numeroDia = (int) $dia->format('N');    // 1 lunes ... 7 domingo
            $base = array_values(array_filter($horarios, fn($h) => (int) ($h['dia'] ?? 0) === $numeroDia));
        }

        $ventanas = [];
        foreach ($base as $tramo) {
            $inicio = self::conHora($dia, (string) $tramo['inicio']);
            $fin = self::conHora($dia, (string) $tramo['fin']);
            if ($inicio && $fin && $fin > $inicio) {
                $ventanas[] = ['inicio' => $inicio, 'fin' => $fin];
            }
        }

        // Recortes parciales del dia (por ejemplo, cerrado de 11:00 a 12:00).
        foreach ($delDia as $excepcion) {
            if (($excepcion['tipo'] ?? '') !== 'cerrado' || empty($excepcion['inicio'])) {
                continue;
            }
            $ventanas = self::restar(
                $ventanas,
                self::conHora($dia, (string) $excepcion['inicio']),
                self::conHora($dia, (string) $excepcion['fin'])
            );
        }

        usort($ventanas, fn($a, $b) => $a['inicio'] <=> $b['inicio']);
        return self::unir($ventanas);
    }

    /**
     * Asigna hora estimada a cada turno en espera.
     *
     * @param array $turnos  [['id','minutos','estado','llamado'], ...] en orden de folio
     * @return array ['estimados' => [id => ?DateTimeImmutable], 'libre' => ?DateTimeImmutable]
     *   'libre' es el primer instante disponible despues de toda la fila.
     */
    public static function calcular(
        DateTimeImmutable $ahora,
        array $ventanas,
        array $bloqueos,
        array $turnos,
        array $opciones = []
    ): array {
        $colchonTurno = (int) ($opciones['colchon_turno'] ?? 2);
        $colchonReunion = (int) ($opciones['colchon_reunion'] ?? 10);
        $bloqueos = self::ordenar($bloqueos);

        $cursor = $ahora;
        $estimados = [];

        foreach ($turnos as $turno) {
            $estado = (string) ($turno['estado'] ?? 'espera');
            $minutos = max(1, (int) ($turno['minutos'] ?? 10));

            if ($estado === 'llamado') {
                // A quien ya esta adentro se le respeta lo que le queda.
                $inicio = $turno['llamado'] instanceof DateTimeImmutable ? $turno['llamado'] : $ahora;
                $estimados[$turno['id']] = $inicio;
                $cursor = self::mayor($ahora, $inicio->modify("+{$minutos} minutes"))
                    ->modify("+{$colchonTurno} minutes");
                continue;
            }
            if ($estado !== 'espera') {
                continue;   // atendidos, cancelados y ausentes no ocupan lugar
            }

            $hueco = self::acomodar($cursor, $minutos, $ventanas, $bloqueos, $colchonReunion);
            $estimados[$turno['id']] = $hueco;
            if ($hueco === null) {
                continue;   // ya no alcanza hoy; los siguientes tampoco
            }
            $cursor = $hueco->modify('+' . ($minutos + $colchonTurno) . ' minutes');
        }

        return ['estimados' => $estimados, 'libre' => $cursor];
    }

    /**
     * Primer instante, a partir de `desde`, donde caben `minutos` completos
     * sin invadir una reunion ni salirse del horario de atencion.
     */
    public static function acomodar(
        DateTimeImmutable $desde,
        int $minutos,
        array $ventanas,
        array $bloqueos,
        int $colchonReunion = 10
    ): ?DateTimeImmutable {
        if (!$ventanas) {
            return null;
        }
        $cursor = $desde;
        $bloqueos = self::ordenar($bloqueos);

        for ($vuelta = 0; $vuelta < 200; $vuelta++) {
            $ventana = self::ventanaPara($cursor, $ventanas);
            if ($ventana === null) {
                return null;                       // ya no queda horario hoy
            }
            if ($cursor < $ventana['inicio']) {
                $cursor = $ventana['inicio'];
            }
            $termina = $cursor->modify("+{$minutos} minutes");
            if ($termina > $ventana['fin']) {
                $siguiente = self::ventanaSiguiente($ventana['fin'], $ventanas);
                if ($siguiente === null) {
                    return null;
                }
                $cursor = $siguiente['inicio'];
                continue;
            }

            $choque = false;
            foreach ($bloqueos as $bloqueo) {
                $protegido = $bloqueo['inicio']->modify("-{$colchonReunion} minutes");
                if ($cursor < $bloqueo['fin'] && $termina > $protegido) {
                    $cursor = $bloqueo['fin'];     // el turno se va despues de la reunion
                    $choque = true;
                    break;
                }
            }
            if (!$choque) {
                return $cursor;
            }
        }
        return null;
    }

    /** Minutos de espera aproximados entre dos instantes, nunca negativos. */
    public static function espera(DateTimeImmutable $ahora, ?DateTimeImmutable $estimado): ?int
    {
        if ($estimado === null) {
            return null;
        }
        $minutos = (int) round(($estimado->getTimestamp() - $ahora->getTimestamp()) / 60);
        return max(0, $minutos);
    }

    // --- apoyos ----------------------------------------------------------

    public static function conHora(DateTimeImmutable $dia, string $hora): ?DateTimeImmutable
    {
        if (!preg_match('/^(\d{1,2}):(\d{2})$/', trim($hora), $partes)) {
            return null;
        }
        return $dia->setTime((int) $partes[1], (int) $partes[2], 0);
    }

    public static function ordenar(array $bloqueos): array
    {
        $limpios = [];
        foreach ($bloqueos as $bloqueo) {
            if ($bloqueo['inicio'] instanceof DateTimeImmutable && $bloqueo['fin'] instanceof DateTimeImmutable
                && $bloqueo['fin'] > $bloqueo['inicio']) {
                $limpios[] = $bloqueo;
            }
        }
        usort($limpios, fn($a, $b) => $a['inicio'] <=> $b['inicio']);
        return $limpios;
    }

    private static function ventanaPara(DateTimeImmutable $momento, array $ventanas): ?array
    {
        foreach ($ventanas as $ventana) {
            if ($momento < $ventana['fin']) {
                return $ventana;   // la que lo contiene o la proxima que abre
            }
        }
        return null;
    }

    private static function ventanaSiguiente(DateTimeImmutable $momento, array $ventanas): ?array
    {
        foreach ($ventanas as $ventana) {
            if ($ventana['inicio'] > $momento) {
                return $ventana;
            }
        }
        return null;
    }

    private static function mayor(DateTimeImmutable $uno, DateTimeImmutable $otro): DateTimeImmutable
    {
        return $uno > $otro ? $uno : $otro;
    }

    private static function restar(array $ventanas, ?DateTimeImmutable $inicio, ?DateTimeImmutable $fin): array
    {
        if ($inicio === null || $fin === null || $fin <= $inicio) {
            return $ventanas;
        }
        $resultado = [];
        foreach ($ventanas as $ventana) {
            if ($fin <= $ventana['inicio'] || $inicio >= $ventana['fin']) {
                $resultado[] = $ventana;
                continue;
            }
            if ($inicio > $ventana['inicio']) {
                $resultado[] = ['inicio' => $ventana['inicio'], 'fin' => $inicio];
            }
            if ($fin < $ventana['fin']) {
                $resultado[] = ['inicio' => $fin, 'fin' => $ventana['fin']];
            }
        }
        return $resultado;
    }

    private static function unir(array $ventanas): array
    {
        $unidas = [];
        foreach ($ventanas as $ventana) {
            $ultima = $unidas ? array_key_last($unidas) : null;
            if ($ultima !== null && $ventana['inicio'] <= $unidas[$ultima]['fin']) {
                $unidas[$ultima]['fin'] = self::mayor($unidas[$ultima]['fin'], $ventana['fin']);
                continue;
            }
            $unidas[] = $ventana;
        }
        return $unidas;
    }
}
