<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/datos.php';

/** Base con horario amplio de hoy, para poder mover la jornada a voluntad. */
function base_con_jornada(string $inicio = '08:00', string $fin = '18:00'): array
{
    return base_de_prueba(['inicio' => $inicio, 'fin' => $fin]);
}

Pruebas::caso('la jornada se propone sola desde el horario semanal', function () {
    $dep = base_con_jornada('09:00', '15:00');
    $hoy = (new DateTimeImmutable('now'))->format('Y-m-d');
    $jornada = jornada($dep, $hoy);

    Pruebas::igual('09:00', $jornada['apertura']);
    Pruebas::igual('15:00', $jornada['cierre']);
    Pruebas::igual('programada', $jornada['estado'], 'todavia no llegas a la oficina');
});

Pruebas::caso('antes de llegar la gente ya puede formarse, pero la atencion esta en pausa', function () {
    $dep = base_con_jornada();
    $estado = fila_estado($dep, momento_hoy('08:30'));

    Pruebas::igual(true, $estado['abierta'], 'si se puede tomar turno');
    Pruebas::igual('pausada', $estado['atencion']);
    Pruebas::igual('08:00', u_hora($estado['no_disponible_hasta']), 'la hora de llegada prevista');
});

Pruebas::caso('al abrir la jornada la atencion queda disponible hasta el cierre', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    $estado = fila_estado($dep, momento_hoy('10:00'));

    Pruebas::igual('atendiendo', $estado['atencion']);
    Pruebas::igual('15:00', u_hora($estado['disponible_hasta']));
    Pruebas::igual(null, $estado['no_disponible_hasta']);
});

Pruebas::caso('una clase o videoconferencia recorta el disponible hasta', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen) VALUES (1,?,?,?,?)',
        [hoy('12:00'), hoy('14:00'), 'Clase', 'manual']);

    $estado = fila_estado($dep, momento_hoy('10:00'));
    Pruebas::igual('atendiendo', $estado['atencion']);
    Pruebas::igual('12:00', u_hora($estado['disponible_hasta']), 'hasta que empieza la clase');
});

Pruebas::caso('durante la clase se muestra hasta que hora no hay atencion', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen) VALUES (1,?,?,?,?)',
        [hoy('12:00'), hoy('14:00'), 'Comida', 'manual']);

    $estado = fila_estado($dep, momento_hoy('12:30'));
    Pruebas::igual('ocupado', $estado['atencion']);
    Pruebas::igual('14:00', u_hora($estado['no_disponible_hasta']));
    Pruebas::igual(null, $estado['disponible_hasta']);
});

Pruebas::caso('si llegas tarde la fila arranca a la hora en que abriste', function () {
    $dep = base_con_jornada('08:00', '15:00');
    crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);
    abrir_jornada($dep, '15:00', null, null, '10:30');   // llegaste a las 10:30

    $jornada = jornada($dep, (new DateTimeImmutable('now'))->format('Y-m-d'));
    Pruebas::igual('10:30', $jornada['apertura']);
    Pruebas::igual('abierta', $jornada['estado']);
    Pruebas::cierto($jornada['abierta_en'] !== null, 'queda constancia de la hora real');

    $estado = fila_estado($dep, momento_hoy('09:00'));
    Pruebas::igual(hoy('10:30'), $estado['turnos'][0]['estimado']->format('Y-m-d H:i'),
        'quien madrugo espera a que llegues');
});

Pruebas::caso('el tope cierra el registro aunque quede jornada', function () {
    $dep = base_con_jornada('08:00', '18:00');
    abrir_jornada($dep, '18:00', '17:00', null, '08:00');

    $antes = fila_estado($dep, momento_hoy('16:30'));
    Pruebas::igual(true, $antes['abierta']);

    $despues = fila_estado($dep, momento_hoy('17:30'));
    Pruebas::igual(false, $despues['abierta']);
    Pruebas::igual('El registro en la cola cerró a las 17:00.', $despues['motivo_cierre']);
    Pruebas::igual('atendiendo', $despues['atencion'], 'sigues atendiendo a los ya formados');
});

Pruebas::caso('sin tope, la cola se cierra cuando el turno ya no alcanza', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    $estado = fila_estado($dep, momento_hoy('14:55'));
    Pruebas::igual(false, $estado['abierta'], 'faltan 5 minutos y un turno dura 10');
    Pruebas::igual('Por hoy ya no alcanza el horario de atención.', $estado['motivo_cierre']);
});

Pruebas::caso('la cola respeta a los que ya estan formados', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    for ($i = 0; $i < 3; $i++) {
        crear_turno($dep, "Persona {$i}", "p{$i}@uaemex.mx", 'Caso', 10);
    }
    // A las 14:30 quedan 30 minutos: los tres formados los ocupan, no cabe uno mas.
    $estado = fila_estado($dep, momento_hoy('14:30'));
    Pruebas::igual(3, count($estado['espera']));
    Pruebas::igual(false, $estado['abierta']);
});

Pruebas::caso('cancelar la cola cancela a todos y devuelve a quien avisar', function () {
    $dep = base_con_jornada();
    abrir_jornada($dep, null, null, null, '08:00');
    crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);
    crear_turno($dep, 'Luis Mora', 'luis@uaemex.mx', 'Caso', 5);

    $afectados = cancelar_cola($dep, 'Salida de emergencia');
    Pruebas::igual(2, count($afectados));
    Pruebas::igual('ana@uaemex.mx', $afectados[0]['email']);

    $estado = fila_estado($dep, momento_hoy('11:00'));
    Pruebas::igual(0, count($estado['espera']));
    Pruebas::igual('cerrada', $estado['atencion']);
    Pruebas::igual('Salida de emergencia', $estado['motivo_cierre']);
});

Pruebas::caso('se puede dejar lista la jornada de manana sin tocar la de hoy', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    $manana = (new DateTimeImmutable('now'))->modify('+1 day')->format('Y-m-d');

    configurar_jornada($dep, $manana, ['apertura' => '10:00', 'cierre' => '14:00', 'tope' => '13:00']);
    $j = jornada($dep, $manana, false);
    Pruebas::igual('10:00', $j['apertura']);
    Pruebas::igual('13:00', $j['tope']);
    Pruebas::igual('programada', $j['estado']);

    $hoy = jornada($dep, (new DateTimeImmutable('now'))->format('Y-m-d'), false);
    Pruebas::igual('abierta', $hoy['estado'], 'la de hoy sigue igual');
});

Pruebas::caso('un dia cancelado no admite a nadie', function () {
    $dep = base_con_jornada();
    configurar_jornada($dep, (new DateTimeImmutable('now'))->format('Y-m-d'),
        ['estado' => 'cancelada', 'nota' => 'Consejo académico todo el día']);

    $estado = fila_estado($dep, momento_hoy('10:00'));
    Pruebas::igual(false, $estado['abierta']);
    Pruebas::igual('sin-atencion', $estado['atencion']);
    Pruebas::igual('Consejo académico todo el día', $estado['motivo_cierre']);
});

Pruebas::caso('las citas confirmadas se pueden listar para cancelarlas', function () {
    $dep = base_con_jornada();
    $cita = crear_cita($dep, 'Sara Díaz', 'sara@uaemex.mx', 'Proyecto', '', 30, hoy('13:00'));
    aprobar_cita($cita);
    Pruebas::igual(1, count(citas_confirmadas((int) $dep['id'])));

    cancelar_cita(cita_por_token($cita['token']), 'titular');
    Pruebas::igual(0, count(citas_confirmadas((int) $dep['id'])));
    Pruebas::igual(0, count(bloqueos(1, momento_hoy('00:00'))), 'el bloque queda libre');
});

Pruebas::caso('la leyenda dice hasta que hora estas disponible', function () {
    $dep = base_con_jornada('08:00', '15:00');
    abrir_jornada($dep, '15:00', null, null, '08:00');
    Pruebas::igual('Disponible hasta 15:00',
        leyenda_atencion(fila_estado($dep, momento_hoy('10:00'))));

    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen) VALUES (1,?,?,?,?)',
        [hoy('12:00'), hoy('14:00'), 'Videoconferencia', 'manual']);
    Pruebas::igual('Disponible hasta 12:00',
        leyenda_atencion(fila_estado($dep, momento_hoy('10:00'))));
    Pruebas::igual('No disponible hasta 14:00',
        leyenda_atencion(fila_estado($dep, momento_hoy('12:30'))));
    Pruebas::igual('Disponible hasta 15:00',
        leyenda_atencion(fila_estado($dep, momento_hoy('14:10'))), 'al terminar, vuelve');
});

Pruebas::caso('la leyenda anuncia la hora de llegada mientras no abres', function () {
    $dep = base_con_jornada('09:00', '15:00');
    Pruebas::igual('Disponible a partir de las 09:00',
        leyenda_atencion(fila_estado($dep, momento_hoy('08:00'))));
});

Pruebas::caso('al cerrar, la leyenda explica el motivo', function () {
    $dep = base_con_jornada();
    cerrar_jornada($dep, 'Salí a una emergencia');
    Pruebas::igual('Salí a una emergencia',
        leyenda_atencion(fila_estado($dep, momento_hoy('13:00'))));

    $otra = base_con_jornada();
    cerrar_jornada($otra);
    Pruebas::igual('La atención de hoy terminó',
        leyenda_atencion(fila_estado($otra, momento_hoy('13:00'))));
});
