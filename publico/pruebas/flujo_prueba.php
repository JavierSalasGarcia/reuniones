<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/datos.php';
require_once __DIR__ . '/../lib/correo.php';

/** Base en memoria con una dependencia abierta todo el dia de hoy. */
function base_de_prueba(array $ajustes = []): array
{
    $pdo = new PDO('sqlite::memory:', null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $pdo->exec(file_get_contents(__DIR__ . '/esquema_sqlite.sql'));
    db_usar($pdo);
    config_usar([
        'zona' => 'America/Mexico_City',
        'base_url' => '/citas',
        'sitio' => 'https://fingenieria.mx/citas',
        'correo' => ['modo' => 'bitacora', 'remitente' => 'citas@fingenieria.mx'],
    ]);
    $GLOBALS['_correos_enviados'] = [];

    consulta('INSERT INTO dependencias (clave, nombre, titular, dominio_correo, token_hash, disponible, '
        . 'duracion_max, colchon_turno, colchon_reunion, minutos_cita, activa, creado) '
        . 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)',
        ['sa', 'Subdirección Académica', 'Javier Salas', 'uaemex.mx',
         hash('sha256', 'secreto'), $ajustes['disponible'] ?? 1, 10, 2, 10, '20,30,45', ahora_texto()]);

    $dia = (int) (new DateTimeImmutable('now'))->format('N');
    consulta('INSERT INTO horarios (dependencia_id, dia, inicio, fin) VALUES (1, ?, ?, ?)',
        [$dia, $ajustes['inicio'] ?? '00:00', $ajustes['fin'] ?? '23:59']);

    return dependencia('sa');
}

function hoy(string $hora): string
{
    return (new DateTimeImmutable('now'))->format('Y-m-d') . ' ' . $hora;
}

function momento_hoy(string $hora): DateTimeImmutable
{
    return new DateTimeImmutable(hoy($hora));
}

Pruebas::caso('los turnos se numeran y se encadenan', function () {
    $dep = base_de_prueba();
    crear_turno($dep, 'Ana Ruiz López', 'ana@uaemex.mx', 'Revalidación', 10);
    crear_turno($dep, 'Luis Mora', 'luis@uaemex.mx', 'Firma', 5);

    $estado = fila_estado($dep, momento_hoy('10:00'));
    Pruebas::igual(2, count($estado['turnos']));
    Pruebas::igual(1, (int) $estado['turnos'][0]['folio']);
    Pruebas::igual(hoy('10:00'), $estado['turnos'][0]['estimado']->format('Y-m-d H:i'));
    Pruebas::igual(hoy('10:12'), $estado['turnos'][1]['estimado']->format('Y-m-d H:i'));
    Pruebas::igual('Ana Ruiz', $estado['turnos'][0]['nombre_publico'], 'la pantalla no expone el nombre completo');
});

Pruebas::caso('una reunion aprobada recorre la fila', function () {
    $dep = base_de_prueba();
    crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);
    crear_turno($dep, 'Luis Mora', 'luis@uaemex.mx', 'Caso', 10);

    $cita = crear_cita($dep, 'Sara Díaz', 'sara@uaemex.mx', 'Proyecto', 'Detalle', 30, hoy('10:20'));
    aprobar_cita($cita);

    $estado = fila_estado($dep, momento_hoy('10:00'));
    Pruebas::igual(hoy('10:00'), $estado['turnos'][0]['estimado']->format('Y-m-d H:i'));
    Pruebas::igual(hoy('10:50'), $estado['turnos'][1]['estimado']->format('Y-m-d H:i'),
        'el segundo turno se va despues de la reunion');
    Pruebas::igual(1, count($estado['bloqueos']));
});

Pruebas::caso('cancelar un turno adelanta a los siguientes', function () {
    $dep = base_de_prueba();
    $uno = crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);
    crear_turno($dep, 'Luis Mora', 'luis@uaemex.mx', 'Caso', 10);

    cancelar_turno($uno);
    $estado = fila_estado($dep, momento_hoy('10:00'));
    Pruebas::igual('cancelado', $estado['turnos'][0]['estado']);
    Pruebas::igual(hoy('10:00'), $estado['turnos'][1]['estimado']->format('Y-m-d H:i'));
});

Pruebas::caso('la fila se cierra cuando el titular no esta disponible', function () {
    $dep = base_de_prueba(['disponible' => 0]);
    $estado = fila_estado($dep, momento_hoy('10:00'));
    Pruebas::igual(false, $estado['abierta']);
    Pruebas::cierto($estado['motivo_cierre'] !== '');
});

Pruebas::caso('la fila se cierra cuando ya no alcanza el horario', function () {
    $dep = base_de_prueba(['inicio' => '09:00', 'fin' => '11:00']);
    $estado = fila_estado($dep, momento_hoy('10:55'));
    Pruebas::igual(false, $estado['abierta'], 'faltan 5 minutos y el turno dura 10');
    Pruebas::igual('Por hoy ya no alcanza el horario de atención.', $estado['motivo_cierre']);
});

Pruebas::caso('no se puede tener dos turnos el mismo dia', function () {
    $dep = base_de_prueba();
    crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);
    Pruebas::igual(1, count(turnos_activos_de(1, 'ana@uaemex.mx')));
    Pruebas::igual(0, count(turnos_activos_de(1, 'otro@uaemex.mx')));
});

Pruebas::caso('el codigo de verificacion guarda y devuelve la solicitud', function () {
    $dep = base_de_prueba();
    $carga = ['tipo' => 'turno', 'nombre' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
              'asunto' => 'Caso', 'minutos' => 10];
    $verificacion = verificacion_crear($dep, 'ana@uaemex.mx', $carga);

    Pruebas::igual(null, verificacion_comprobar($dep, 'ana@uaemex.mx', '000000'), 'codigo equivocado');
    $recuperada = verificacion_comprobar($dep, 'ana@uaemex.mx', $verificacion['codigo']);
    Pruebas::igual('Ana Ruiz', $recuperada['nombre'] ?? '');
    Pruebas::igual(null, verificacion_comprobar($dep, 'ana@uaemex.mx', $verificacion['codigo']),
        'un codigo sirve una sola vez');
});

Pruebas::caso('el freno contra abuso cuenta por correo', function () {
    $dep = base_de_prueba();
    for ($i = 0; $i < 5; $i++) {
        verificacion_crear($dep, 'ana@uaemex.mx', ['tipo' => 'turno']);
    }
    Pruebas::cierto(demasiadas_solicitudes('ana@uaemex.mx', '10.0.0.1'));
    Pruebas::igual(false, demasiadas_solicitudes('otra@uaemex.mx', '10.0.0.2'));
});

Pruebas::caso('los huecos para agendar respetan lo ya ocupado', function () {
    $dep = base_de_prueba();
    $dias = huecos($dep, 30, 3, 4);
    Pruebas::cierto(count($dias) > 0, 'hay dias con lugar');
    $primero = $dias[0]['opciones'][0];
    Pruebas::cierto($primero > new DateTimeImmutable('now'), 'nunca ofrece una hora pasada');

    $cita = crear_cita($dep, 'Sara Díaz', 'sara@uaemex.mx', 'Proyecto', '', 30,
        $primero->format('Y-m-d H:i:s'));
    aprobar_cita($cita);
    $nuevos = huecos($dep, 30, 3, 4);
    $repetido = false;
    foreach ($nuevos as $dia) {
        foreach ($dia['opciones'] as $opcion) {
            if ($opcion->format('Y-m-d H:i') === $primero->format('Y-m-d H:i')) {
                $repetido = true;
            }
        }
    }
    Pruebas::igual(false, $repetido, 'la hora aprobada ya no se ofrece');
});

Pruebas::caso('rechazar una cita libera su bloque', function () {
    $dep = base_de_prueba();
    $cita = crear_cita($dep, 'Sara Díaz', 'sara@uaemex.mx', 'Proyecto', '', 30, hoy('10:20'));
    aprobar_cita($cita);
    Pruebas::igual(1, count(bloqueos(1, momento_hoy('00:00'))));

    rechazar_cita(cita_por_token($cita['token']), 'Ese día estaré en Toluca');
    Pruebas::igual(0, count(bloqueos(1, momento_hoy('00:00'))));
    Pruebas::igual('rechazada', cita_por_token($cita['token'])['estado']);
});

Pruebas::caso('los correos se arman con la informacion correcta', function () {
    $dep = base_de_prueba();
    $turno = crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Revalidación', 10);
    correo_turno($dep, $turno, momento_hoy('10:30'), 'https://fingenieria.mx/citas/t/' . $turno['token']);

    $ultimo = end($GLOBALS['_correos_enviados']);
    Pruebas::igual('ana@uaemex.mx', $ultimo['para']);
    Pruebas::cierto(str_contains($ultimo['cuerpo'], '10:30'), 'lleva la hora estimada');
    Pruebas::cierto(str_contains($ultimo['cuerpo'], $turno['token']), 'lleva el enlace para cancelar');
});

Pruebas::caso('quien esta siendo atendido aparece como turno actual', function () {
    $dep = base_de_prueba();
    $turno = crear_turno($dep, 'Ana Ruiz', 'ana@uaemex.mx', 'Caso', 10);
    consulta('UPDATE turnos SET estado = ?, llamado = ? WHERE id = ?',
        ['llamado', hoy('10:02'), $turno['id']]);

    $estado = fila_estado($dep, momento_hoy('10:05'));
    Pruebas::cierto($estado['actual'] !== null);
    Pruebas::igual(1, (int) $estado['actual']['folio']);
    Pruebas::igual(0, count($estado['espera']));
});
