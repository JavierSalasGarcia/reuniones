<?php
/**
 * Copia este archivo como config.php en el servidor y ajusta los datos.
 * No lo subas al repositorio: lleva la contraseña de la base y la del panel.
 */
return [
    'db' => [
        'dsn' => 'mysql:host=localhost;dbname=TU_BASE;charset=utf8mb4',
        'usuario' => 'TU_USUARIO',
        'clave' => 'TU_CONTRASENA',
    ],

    // Direccion base del sitio, tal como la ve la gente.
    'sitio' => 'https://fingenieria.mx/citas',
    'base_url' => '/citas',
    'zona' => 'America/Mexico_City',

    // Contraseña del panel de administracion. Generala con:
    //   php -r "echo password_hash('tu contraseña', PASSWORD_DEFAULT);"
    'admin_hash' => '',

    // Correos de la fila (codigo de verificacion, confirmaciones y avisos).
    // Salen desde un buzon del hosting; la minuta se envia aparte desde la
    // laptop con la cuenta institucional.
    'correo' => [
        'modo' => 'mail',                 // mail | smtp | bitacora
        'remitente' => 'citas@fingenieria.mx',
        'remitente_nombre' => 'Agenda de la Facultad',
        'responder_a' => '',
        'servidor' => 'mail.fingenieria.mx',
        'puerto' => 587,
        'usuario' => '',
        'clave' => '',
    ],
];
