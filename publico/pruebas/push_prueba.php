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
