<?php
declare(strict_types=1);

Pruebas::caso('solo se aceptan correos institucionales', function () {
    Pruebas::cierto(u_email_valido('alguien@uaemex.mx', 'uaemex.mx'));
    Pruebas::cierto(u_email_valido('ALGUIEN@Alumno.UAEMex.mx', 'uaemex.mx'), 'subdominio y mayusculas');
    Pruebas::igual(false, u_email_valido('alguien@gmail.com', 'uaemex.mx'));
    Pruebas::igual(false, u_email_valido('alguien@nouaemex.mx', 'uaemex.mx'), 'no basta terminar igual');
    Pruebas::igual(false, u_email_valido('sin arroba', 'uaemex.mx'));
});

Pruebas::caso('el nombre publico se acorta', function () {
    Pruebas::igual('Ana Ruiz', u_nombre_corto('Ana Ruiz López Quintana'));
    Pruebas::igual('Luis Mora', u_nombre_corto('Luis Mora'));
    Pruebas::igual('Sara', u_nombre_corto('  Sara  '));
});

Pruebas::caso('el texto que llega de fuera se limpia', function () {
    Pruebas::igual('hola mundo', u_limpio("  hola\n  mundo "));
    Pruebas::igual('alert(1)', u_limpio('<script>alert(1)</script>'));
    Pruebas::igual('abc', u_limpio('abcdef', 3));
});

Pruebas::caso('la espera se dice en palabras', function () {
    Pruebas::igual('ahora', u_espera_en_palabras(0));
    Pruebas::igual('en unos 25 minutos', u_espera_en_palabras(25));
    Pruebas::igual('en una hora y 15 minutos', u_espera_en_palabras(75));
    Pruebas::igual('en 2 horas', u_espera_en_palabras(122));
    Pruebas::igual('sin hora todavía', u_espera_en_palabras(null));
});

Pruebas::caso('los tokens son largos y distintos', function () {
    Pruebas::igual(32, strlen(u_token()));
    Pruebas::cierto(u_token() !== u_token());
    Pruebas::igual(6, strlen(u_codigo()));
});
