<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/push.php';

/** Dependencia con el aviso al celular ya configurado. */
function base_con_push(bool $detalle = true): array
{
    $dep = base_de_prueba();
    config_usar(array_merge(config(), ['push' => ['modo' => 'bitacora'], 'sitio' => 'https://fingenieria.mx/citas']));
    consulta('UPDATE dependencias SET push_tema = ?, push_detalle = ? WHERE id = 1',
        ['sa-9f3c1a7b2d', $detalle ? 1 : 0]);
    $GLOBALS['_push_enviados'] = [];
    return dependencia('sa');
}

Pruebas::caso('sin tema configurado no se manda ningun aviso', function () {
    $dep = base_de_prueba();
    config_usar(array_merge(config(), ['push' => ['modo' => 'bitacora']]));
    $turno = crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);

    Pruebas::igual(false, push_configurado($dep));
    Pruebas::igual(false, push_turno_nuevo($dep, $turno));
    Pruebas::igual(0, count($GLOBALS['_push_enviados']));
});

Pruebas::caso('el aviso trae quien es, de que y a que hora le tocaria', function () {
    $dep = base_con_push();
    $turno = crear_turno($dep, 'Ana Ruiz López', 'ana@uaemex.mx', 'Revalidación', 10);
    Pruebas::cierto(push_turno_nuevo($dep, $turno, momento_hoy('11:20')));

    $aviso = end($GLOBALS['_push_enviados']);
    Pruebas::igual('sa-9f3c1a7b2d', $aviso['tema']);
    Pruebas::igual('Turno 1 · Ana Ruiz', $aviso['titulo']);
    Pruebas::igual('Revalidación · 10 min · le tocaría 11:20', $aviso['mensaje']);
    Pruebas::igual('https://fingenieria.mx/citas/sa/fila', $aviso['abrir']);
});

Pruebas::caso('se puede avisar sin exponer el nombre ni el asunto', function () {
    $dep = base_con_push(false);
    $turno = crear_turno($dep, 'Ana Ruiz López', 'ana@uaemex.mx', 'Caso delicado', 5);
    push_turno_nuevo($dep, $turno, momento_hoy('11:20'));

    $aviso = end($GLOBALS['_push_enviados']);
    Pruebas::igual('Nuevo turno 1', $aviso['titulo']);
    Pruebas::igual('5 min · le tocaría 11:20', $aviso['mensaje']);
    Pruebas::igual(false, str_contains($aviso['mensaje'], 'delicado'));
});

Pruebas::caso('sin hora estimada el aviso igual sale', function () {
    $dep = base_con_push();
    $turno = crear_turno($dep, 'Luis Mora', 'luis@uaemex.mx', 'Beca', 5);
    push_turno_nuevo($dep, $turno);
    Pruebas::igual('Beca · 5 min', end($GLOBALS['_push_enviados'])['mensaje']);
});

Pruebas::caso('el titulo viaja sin acentos ni saltos de linea', function () {
    Pruebas::igual('Turno 3 - Jose Ramirez', push_cabecera("Turno 3 - José Ramírez"));
    Pruebas::igual('dos lineas', push_cabecera("dos\nlineas"));
});

Pruebas::caso('el modo apagado deja todo en silencio', function () {
    $dep = base_con_push();
    config_usar(array_merge(config(), ['push' => ['modo' => 'off']]));
    Pruebas::igual(false, push_configurado($dep));
    Pruebas::igual(false, push_enviar($dep, 'Hola', 'Mundo'));
});

Pruebas::caso('la llave del reloj solo abre la vista del reloj', function () {
    base_de_prueba();
    consulta('UPDATE dependencias SET token_hash = ?, token_reloj_hash = ? WHERE id = 1',
        [hash('sha256', 'de-la-laptop'), hash('sha256', 'del-reloj')]);
    $dep = dependencia('sa');

    Pruebas::cierto(token_permite($dep, 'de-la-laptop', 'estado'), 'la laptop puede todo');
    Pruebas::cierto(token_permite($dep, 'de-la-laptop', 'reloj'));
    Pruebas::cierto(token_permite($dep, 'del-reloj', 'reloj'));
    Pruebas::igual(false, token_permite($dep, 'del-reloj', 'estado'));
    Pruebas::igual(false, token_permite($dep, 'del-reloj', 'turno'), 'el reloj no llama turnos');
    Pruebas::igual(false, token_permite($dep, 'inventado', 'reloj'));
    Pruebas::igual(false, token_permite($dep, '', 'reloj'));
});

Pruebas::caso('sin llave de reloj configurada nadie entra por esa puerta', function () {
    base_de_prueba();
    consulta('UPDATE dependencias SET token_hash = ?, token_reloj_hash = ? WHERE id = 1',
        [hash('sha256', 'de-la-laptop'), '']);
    $dep = dependencia('sa');
    Pruebas::igual(false, token_permite($dep, '', 'reloj'));
    Pruebas::cierto(token_permite($dep, 'de-la-laptop', 'reloj'));
});

// --- avisos que dependen de la hora --------------------------------------

/** Dependencia con avisos encendidos y la jornada abierta desde las 08:00. */
function base_con_avisos(string $avisos = 'formado,excedido,cita,vacia', bool $detalle = true): array
{
    $dep = base_con_push($detalle);
    consulta('UPDATE dependencias SET push_avisos = ? WHERE id = 1', [$avisos]);
    $dep = dependencia('sa');
    abrir_jornada($dep, '20:00', null, null, '08:00');
    $GLOBALS['_push_enviados'] = [];
    return dependencia('sa');
}

function atendiendo_desde(array $dep, string $hora, int $minutos = 10): array
{
    $turno = crear_turno($dep, 'Ana Ruiz López', 'ana@uaemex.mx', 'Revalidación', $minutos);
    consulta('UPDATE turnos SET estado = ?, llamado = ? WHERE id = ?',
        ['llamado', hoy($hora), $turno['id']]);
    return $turno;
}

Pruebas::caso('avisa una sola vez cuando la reunion se pasa del tiempo', function () {
    $dep = base_con_avisos();
    atendiendo_desde($dep, '11:00', 10);

    $aTiempo = avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:05')));
    Pruebas::igual(0, count($aTiempo), 'a los cinco minutos todavia no');

    $pasado = avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:16')));
    Pruebas::igual(1, count($pasado));
    $aviso = end($GLOBALS['_push_enviados']);
    Pruebas::igual('Se pasó el tiempo · Ana Ruiz', $aviso['titulo']);
    Pruebas::igual('Llevan 16 de 10 minutos', $aviso['mensaje']);

    $otraVuelta = avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:20')));
    Pruebas::igual(0, count($otraVuelta), 'no vuelve a vibrar por lo mismo');
});

Pruebas::caso('avisa cinco minutos antes de una reunion agendada', function () {
    $dep = base_con_avisos();
    $cita = crear_cita($dep, 'Sara Díaz Ortega', 'sara@uaemex.mx', 'Proyecto', '', 30, hoy('11:20'));
    aprobar_cita($cita);

    Pruebas::igual(0, count(avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:00')))),
        'veinte minutos antes todavia no');

    $cerca = avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:16')));
    Pruebas::igual(1, count($cerca));
    $aviso = end($GLOBALS['_push_enviados']);
    Pruebas::igual('A las 11:20, en 4 min', $aviso['titulo']);
    Pruebas::igual('Sara Díaz · Proyecto', $aviso['mensaje']);

    Pruebas::igual(0, count(avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:18')))),
        'no repite el mismo bloque');
});

Pruebas::caso('el aviso de la clase o la comida usa su motivo', function () {
    $dep = base_con_avisos();
    consulta('INSERT INTO bloqueos (dependencia_id, inicio, fin, motivo, origen) VALUES (1,?,?,?,?)',
        [hoy('13:00'), hoy('14:00'), 'Clase de Estructuras', 'manual']);

    avisos_del_momento($dep, fila_estado($dep, momento_hoy('12:57')));
    Pruebas::igual('Clase de Estructuras', end($GLOBALS['_push_enviados'])['mensaje']);
});

Pruebas::caso('avisa cuando la cola se queda vacia', function () {
    $dep = base_con_avisos();
    $turno = crear_turno($dep, 'Luis Mora', 'luis@uaemex.mx', 'Beca', 5);

    Pruebas::igual(0, count(avisos_del_momento($dep, fila_estado($dep, momento_hoy('10:00')))),
        'con gente esperando no dice nada');

    cancelar_turno($turno);
    $vacia = avisos_del_momento($dep, fila_estado($dep, momento_hoy('10:05')));
    Pruebas::igual(['vacia'], $vacia);
    Pruebas::igual('Cola vacía', end($GLOBALS['_push_enviados'])['titulo']);

    Pruebas::igual(0, count(avisos_del_momento($dep, fila_estado($dep, momento_hoy('10:10')))),
        'ya vacia, no insiste');
});

Pruebas::caso('sin haber tenido gente no avisa que esta vacia', function () {
    $dep = base_con_avisos();
    avisos_del_momento($dep, fila_estado($dep, momento_hoy('09:00')));
    $segunda = avisos_del_momento($dep, fila_estado($dep, momento_hoy('09:05')));
    Pruebas::igual(0, count($segunda), 'la cola nunca tuvo a nadie');
});

Pruebas::caso('cada aviso se puede apagar por separado', function () {
    $dep = base_con_avisos('formado');   // solo el de alguien se forma
    atendiendo_desde($dep, '11:00', 10);
    $cita = crear_cita($dep, 'Sara Díaz', 'sara@uaemex.mx', 'Proyecto', '', 30, hoy('11:20'));
    aprobar_cita($cita);

    Pruebas::igual(0, count(avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:16')))));
    Pruebas::igual(false, push_activo($dep, 'excedido'));
    Pruebas::cierto(push_activo($dep, 'formado'));
});

Pruebas::caso('los avisos tambien pueden ir sin nombres', function () {
    $dep = base_con_avisos('formado,excedido,cita,vacia', false);
    atendiendo_desde($dep, '11:00', 10);
    avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:16')));

    $aviso = end($GLOBALS['_push_enviados']);
    Pruebas::igual('Se pasó el tiempo · Turno 1', $aviso['titulo']);
    Pruebas::igual(false, str_contains($aviso['titulo'], 'Ana'));
});

Pruebas::caso('sin tema configurado no se revisa nada', function () {
    $dep = base_de_prueba();
    config_usar(array_merge(config(), ['push' => ['modo' => 'bitacora']]));
    abrir_jornada($dep, '20:00', null, null, '08:00');
    $dep = dependencia('sa');
    Pruebas::igual(0, count(avisos_del_momento($dep, fila_estado($dep, momento_hoy('11:00')))));
});
