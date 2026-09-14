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

    // Correo de la fila (codigo de verificacion, confirmaciones y avisos).
    // Sale por SMTP desde el buzon de fingenieria.mx, igual que el correo que
    // manda la laptop.
    'correo' => [
        'modo' => 'smtp',                 // smtp | mail | bitacora
        'servidor' => 'mail.fingenieria.mx',
        'puerto' => 587,
        'usuario' => 'citas@fingenieria.mx',
        'clave' => '',
        'remitente' => 'citas@fingenieria.mx',
        'remitente_nombre' => 'Agenda de la Facultad',
        'responder_a' => '',              // opcional: tu correo institucional
    ],
];
