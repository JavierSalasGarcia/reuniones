<?php
declare(strict_types=1);

function momento(string $texto): DateTimeImmutable
{
    return new DateTimeImmutable($texto);
}

function turno(int $id, int $minutos = 10, string $estado = 'espera', ?string $llamado = null): array
{
    return ['id' => $id, 'minutos' => $minutos, 'estado' => $estado,
            'llamado' => $llamado ? momento($llamado) : null];
}

function bloqueo(string $inicio, string $fin, string $motivo = 'Reunion'): array
{
    return ['inicio' => momento($inicio), 'fin' => momento($fin), 'motivo' => $motivo];
}

$horarioTipico = [
    ['dia' => 1, 'inicio' => '09:00', 'fin' => '14:00'],
    ['dia' => 2, 'inicio' => '09:00', 'fin' => '11:00'],
    ['dia' => 2, 'inicio' => '12:00', 'fin' => '14:00'],
];
$opciones = ['colchon_turno' => 2, 'colchon_reunion' => 10];

Pruebas::caso('la fila encadena turnos con su colchon', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $salida = Agenda::calcular(momento('2026-09-14 10:00'), $ventanas, [],
        [turno(1), turno(2), turno(3)], $opciones);

    Pruebas::igual('2026-09-14 10:00', $salida['estimados'][1]);
    Pruebas::igual('2026-09-14 10:12', $salida['estimados'][2]);
    Pruebas::igual('2026-09-14 10:24', $salida['estimados'][3]);
});

Pruebas::caso('un turno corto ocupa menos lugar', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $salida = Agenda::calcular(momento('2026-09-14 10:00'), $ventanas, [],
        [turno(1, 5), turno(2, 5), turno(3, 10)], $opciones);

    Pruebas::igual('2026-09-14 10:07', $salida['estimados'][2]);
    Pruebas::igual('2026-09-14 10:14', $salida['estimados'][3]);
});

Pruebas::caso('la reunion agendada empuja los turnos que no alcanzan', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $reunion = [bloqueo('2026-09-14 10:30', '2026-09-14 11:00')];
    $salida = Agenda::calcular(momento('2026-09-14 10:00'), $ventanas, $reunion,
        [turno(1), turno(2), turno(3)], $opciones);

    Pruebas::igual('2026-09-14 10:00', $salida['estimados'][1]);
    Pruebas::igual('2026-09-14 11:00', $salida['estimados'][2],
        'terminaria 10:22 y el colchon empieza 10:20');
    Pruebas::igual('2026-09-14 11:12', $salida['estimados'][3]);
});

Pruebas::caso('un turno corto si alcanza antes de la reunion', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $reunion = [bloqueo('2026-09-14 10:30', '2026-09-14 11:00')];
    $salida = Agenda::calcular(momento('2026-09-14 10:00'), $ventanas, $reunion,
        [turno(1, 10), turno(2, 5)], $opciones);

    Pruebas::igual('2026-09-14 10:00', $salida['estimados'][1]);
    Pruebas::igual('2026-09-14 10:12', $salida['estimados'][2], 'termina 10:17, antes del colchon');
});

Pruebas::caso('el colchon de diez minutos protege el inicio de la reunion', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $reunion = [bloqueo('2026-09-14 10:25', '2026-09-14 11:00')];
    $salida = Agenda::calcular(momento('2026-09-14 10:10'), $ventanas, $reunion,
        [turno(1, 10)], $opciones);

    Pruebas::igual('2026-09-14 11:00', $salida['estimados'][1],
        'terminaria 10:20 y el colchon empieza 10:15');
});

Pruebas::caso('una reunion en curso manda la fila a su termino', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $reunion = [bloqueo('2026-09-14 10:00', '2026-09-14 10:45')];
    $salida = Agenda::calcular(momento('2026-09-14 10:20'), $ventanas, $reunion,
        [turno(1), turno(2)], $opciones);

    Pruebas::igual('2026-09-14 10:45', $salida['estimados'][1]);
    Pruebas::igual('2026-09-14 10:57', $salida['estimados'][2]);
});

Pruebas::caso('quien ya esta adentro conserva su lugar', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $salida = Agenda::calcular(momento('2026-09-14 10:08'), $ventanas, [],
        [turno(1, 10, 'llamado', '2026-09-14 10:05'), turno(2)], $opciones);

    Pruebas::igual('2026-09-14 10:05', $salida['estimados'][1]);
    Pruebas::igual('2026-09-14 10:17', $salida['estimados'][2]);
});

Pruebas::caso('los atendidos y cancelados no ocupan lugar', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 14:00')]];
    $salida = Agenda::calcular(momento('2026-09-14 10:00'), $ventanas, [],
        [turno(1, 10, 'atendido'), turno(2, 10, 'cancelado'), turno(3)], $opciones);

    Pruebas::igual('2026-09-14 10:00', $salida['estimados'][3]);
    Pruebas::cierto(!isset($salida['estimados'][1]));
});

Pruebas::caso('lo que ya no alcanza hoy se queda sin hora', function () use ($opciones) {
    $ventanas = [['inicio' => momento('2026-09-14 09:00'), 'fin' => momento('2026-09-14 10:00')]];
    $salida = Agenda::calcular(momento('2026-09-14 09:40'), $ventanas, [],
        [turno(1), turno(2), turno(3)], $opciones);

    Pruebas::igual('2026-09-14 09:40', $salida['estimados'][1]);
    Pruebas::igual(null, $salida['estimados'][2], 'terminaria 10:02 y el horario cierra a las 10:00');
    Pruebas::igual(null, $salida['estimados'][3]);
});

Pruebas::caso('la fila salta al segundo horario del dia', function () use ($opciones) {
    $ventanas = [
        ['inicio' => momento('2026-09-15 09:00'), 'fin' => momento('2026-09-15 11:00')],
        ['inicio' => momento('2026-09-15 12:00'), 'fin' => momento('2026-09-15 14:00')],
    ];
    $salida = Agenda::calcular(momento('2026-09-15 10:50'), $ventanas, [],
        [turno(1), turno(2)], $opciones);

    Pruebas::igual('2026-09-15 10:50', $salida['estimados'][1]);
    Pruebas::igual('2026-09-15 12:00', $salida['estimados'][2]);
});

Pruebas::caso('las ventanas salen del horario semanal', function () use ($horarioTipico) {
    $lunes = Agenda::ventanas(momento('2026-09-14 00:00'), $horarioTipico);
    Pruebas::igual(1, count($lunes));
    Pruebas::igual('2026-09-14 09:00', $lunes[0]['inicio']);

    $martes = Agenda::ventanas(momento('2026-09-15 00:00'), $horarioTipico);
    Pruebas::igual(2, count($martes));
    Pruebas::igual('2026-09-15 12:00', $martes[1]['inicio']);

    $sabado = Agenda::ventanas(momento('2026-09-19 00:00'), $horarioTipico);
    Pruebas::igual(0, count($sabado));
});

Pruebas::caso('una excepcion cierra el dia completo', function () use ($horarioTipico) {
    $ventanas = Agenda::ventanas(momento('2026-09-14 00:00'), $horarioTipico,
        [['fecha' => '2026-09-14', 'tipo' => 'cerrado', 'inicio' => null, 'fin' => null]]);
    Pruebas::igual(0, count($ventanas));
});

Pruebas::caso('una excepcion parcial recorta el horario', function () use ($horarioTipico) {
    $ventanas = Agenda::ventanas(momento('2026-09-14 00:00'), $horarioTipico,
        [['fecha' => '2026-09-14', 'tipo' => 'cerrado', 'inicio' => '11:00', 'fin' => '12:00']]);
    Pruebas::igual(2, count($ventanas));
    Pruebas::igual('2026-09-14 11:00', $ventanas[0]['fin']);
    Pruebas::igual('2026-09-14 12:00', $ventanas[1]['inicio']);
});

Pruebas::caso('un horario especial sustituye al de la semana', function () use ($horarioTipico) {
    $ventanas = Agenda::ventanas(momento('2026-09-19 00:00'), $horarioTipico,
        [['fecha' => '2026-09-19', 'tipo' => 'abierto', 'inicio' => '10:00', 'fin' => '12:00']]);
    Pruebas::igual(1, count($ventanas));
    Pruebas::igual('2026-09-19 10:00', $ventanas[0]['inicio']);
});

Pruebas::caso('sin horario no hay donde acomodar', function () {
    Pruebas::igual(null, Agenda::acomodar(momento('2026-09-14 10:00'), 10, [], []));
});

Pruebas::caso('la espera nunca es negativa', function () {
    Pruebas::igual(0, Agenda::espera(momento('2026-09-14 10:00'), momento('2026-09-14 09:50')));
    Pruebas::igual(25, Agenda::espera(momento('2026-09-14 10:00'), momento('2026-09-14 10:25')));
    Pruebas::igual(null, Agenda::espera(momento('2026-09-14 10:00'), null));
});
