<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/datos.php';
require_once __DIR__ . '/../lib/correo.php';

function base_con_minutas(): array
{
    $dep = base_de_prueba();
    $temporal = sys_get_temp_dir() . '/pruebas-minutas-' . bin2hex(random_bytes(4));
    mkdir($temporal, 0770, true);
    config_usar(array_merge(config(), ['carpeta_subidas' => $temporal]));
    return $dep;
}

function pdf_falso(string $contenido = 'minuta de prueba'): string
{
    $ruta = sys_get_temp_dir() . '/minuta-' . bin2hex(random_bytes(4)) . '.pdf';
    file_put_contents($ruta, "%PDF-1.4\n" . $contenido);
    return $ruta;
}

Pruebas::caso('la minuta se guarda en el expediente de la persona', function () {
    $dep = base_con_minutas();
    $minuta = guardar_minuta($dep, [
        'persona' => 'Ana Ruiz López', 'email' => 'ana@uaemex.mx',
        'asunto' => 'Revalidación', 'fecha' => '2026-09-14 10:30:00', 'reunion_local' => 12,
    ], pdf_falso());

    Pruebas::igual('guardada', $minuta['estado']);
    Pruebas::igual('ana@uaemex.mx', $minuta['email']);
    Pruebas::igual(12, (int) $minuta['reunion_local']);
    Pruebas::cierto(str_contains($minuta['archivo'], 'minutas/sa/ana-uaemex-mx'),
        'queda agrupada por persona');
    Pruebas::cierto(is_file(ruta_subida($minuta['archivo'])), 'el archivo existe en disco');
    Pruebas::igual('20260914_1030_minuta_ana-ruiz-lopez.pdf', $minuta['nombre']);
});

Pruebas::caso('subir dos veces la misma minuta no la duplica', function () {
    $dep = base_con_minutas();
    $datos = ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx', 'asunto' => 'Caso',
              'fecha' => '2026-09-14 10:30:00'];
    $una = guardar_minuta($dep, $datos, pdf_falso('mismo contenido'));
    $otra = guardar_minuta($dep, $datos, pdf_falso('mismo contenido'));

    Pruebas::igual((int) $una['id'], (int) $otra['id']);
    Pruebas::igual(1, (int) fila_una('SELECT COUNT(*) AS n FROM minutas')['n']);
});

Pruebas::caso('una minuta corregida si crea un registro nuevo', function () {
    $dep = base_con_minutas();
    $datos = ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx', 'asunto' => 'Caso',
              'fecha' => '2026-09-14 10:30:00'];
    guardar_minuta($dep, $datos, pdf_falso('version uno'));
    guardar_minuta($dep, $datos, pdf_falso('version dos'));
    Pruebas::igual(2, (int) fila_una('SELECT COUNT(*) AS n FROM minutas')['n']);
});

Pruebas::caso('el correo de la minuta sale del servidor con el PDF adjunto', function () {
    $dep = base_con_minutas();
    $minuta = guardar_minuta($dep, [
        'persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx', 'asunto' => 'Revalidación',
        'fecha' => '2026-09-14 10:30:00',
    ], pdf_falso());

    Pruebas::cierto(correo_minuta($dep, $minuta, 'ana@uaemex.mx'));
    $ultimo = end($GLOBALS['_correos_enviados']);
    Pruebas::igual('ana@uaemex.mx', $ultimo['para']);
    Pruebas::igual(1, count($ultimo['adjuntos']));
    Pruebas::cierto(str_contains($ultimo['asunto'], '14/09/2026'));
    Pruebas::cierto(str_contains($ultimo['cuerpo'], 'Javier Salas'), 'lo firma el titular');
});

Pruebas::caso('el mensaje propio sustituye al texto estandar', function () {
    $dep = base_con_minutas();
    $minuta = guardar_minuta($dep, ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
                                    'fecha' => '2026-09-14 10:30:00'], pdf_falso());
    correo_minuta($dep, $minuta, 'ana@uaemex.mx', 'Va la minuta, con el acuerdo al final.');
    $ultimo = end($GLOBALS['_correos_enviados']);
    Pruebas::igual('Va la minuta, con el acuerdo al final.', $ultimo['cuerpo']);
});

Pruebas::caso('el envio queda registrado en la minuta', function () {
    $dep = base_con_minutas();
    $minuta = guardar_minuta($dep, ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
                                    'fecha' => '2026-09-14 10:30:00'], pdf_falso());
    marcar_minuta((int) $minuta['id'], true, 'ana@uaemex.mx', 'enviada desde el servidor');

    $fresca = minuta((int) $minuta['id'], (int) $dep['id']);
    Pruebas::igual('enviada', $fresca['estado']);
    Pruebas::cierto($fresca['enviado'] !== null);

    marcar_minuta((int) $minuta['id'], false, 'ana@uaemex.mx', 'buzon lleno');
    $fallida = minuta((int) $minuta['id'], (int) $dep['id']);
    Pruebas::igual('error', $fallida['estado']);
    Pruebas::igual('buzon lleno', $fallida['detalle']);
});

Pruebas::caso('el expediente del servidor se consulta por persona', function () {
    $dep = base_con_minutas();
    guardar_minuta($dep, ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
                          'fecha' => '2026-09-14 10:30:00'], pdf_falso('uno'));
    guardar_minuta($dep, ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
                          'fecha' => '2026-10-01 09:00:00'], pdf_falso('dos'));
    guardar_minuta($dep, ['persona' => 'Luis Mora', 'email' => 'luis@uaemex.mx',
                          'fecha' => '2026-09-20 09:00:00'], pdf_falso('tres'));

    Pruebas::igual(2, count(minutas_de((int) $dep['id'], 'ana@uaemex.mx')));
    Pruebas::igual(3, count(minutas_de((int) $dep['id'])));
    $deAna = minutas_de((int) $dep['id'], 'ANA@uaemex.mx');
    Pruebas::igual('2026-10-01 09:00:00', $deAna[0]['fecha'], 'la mas reciente primero');
});

Pruebas::caso('borrar la minuta quita tambien el archivo', function () {
    $dep = base_con_minutas();
    $minuta = guardar_minuta($dep, ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
                                    'fecha' => '2026-09-14 10:30:00'], pdf_falso());
    $ruta = ruta_subida($minuta['archivo']);
    borrar_minuta($minuta);
    Pruebas::igual(false, is_file($ruta));
    Pruebas::igual(0, count(minutas_de((int) $dep['id'])));
});

Pruebas::caso('la retencion solo actua si se configura', function () {
    $dep = base_con_minutas();
    $minuta = guardar_minuta($dep, ['persona' => 'Ana Ruiz', 'email' => 'ana@uaemex.mx',
                                    'fecha' => '2026-09-14 10:30:00'], pdf_falso());
    consulta('UPDATE minutas SET creado = ? WHERE id = ?',
        [(new DateTimeImmutable('now'))->modify('-400 days')->format('Y-m-d H:i:s'), $minuta['id']]);

    Pruebas::igual(0, limpiar_minutas($dep, 0), 'con 0 dias se conservan siempre');
    Pruebas::igual(1, limpiar_minutas($dep, 365));
    Pruebas::igual(0, count(minutas_de((int) $dep['id'])));
});

Pruebas::caso('el mensaje con adjunto se arma como multipart', function () {
    $pdf = pdf_falso('contenido del pdf');
    $armado = correo_armar('Texto del mensaje', [
        ['nombre' => 'minuta.pdf', 'ruta' => $pdf, 'tipo' => 'application/pdf'],
    ]);

    Pruebas::cierto(str_starts_with($armado['tipo'], 'multipart/mixed; boundary='));
    Pruebas::cierto(str_contains($armado['cuerpo'], 'Texto del mensaje'));
    Pruebas::cierto(str_contains($armado['cuerpo'], 'Content-Disposition: attachment; filename="minuta.pdf"'));
    Pruebas::cierto(str_contains($armado['cuerpo'], base64_encode("%PDF-1.4\ncontenido del pdf")));
});

Pruebas::caso('sin adjuntos el mensaje sigue siendo texto simple', function () {
    $armado = correo_armar('Solo texto');
    Pruebas::igual('text/plain; charset=UTF-8', $armado['tipo']);
    Pruebas::igual('Solo texto', $armado['cuerpo']);
});

Pruebas::caso('un adjunto que no existe se ignora en lugar de romper el envio', function () {
    $armado = correo_armar('Texto', [['nombre' => 'fantasma.pdf', 'ruta' => '/no/existe.pdf']]);
    Pruebas::igual('text/plain; charset=UTF-8', $armado['tipo']);
});
