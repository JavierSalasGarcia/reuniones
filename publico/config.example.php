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

    // Cuantos dias se conservan las minutas en el servidor. 0 = para siempre,
    // que es lo que conviene si quieres el expediente disponible desde aqui.
    'minutas_dias' => 0,

    // Aviso al celular (y de ahi al reloj) cuando alguien se forma en la cola.
    // modo: ntfy | bitacora | off.  El tema de cada dependencia se define en
    // el panel de administracion y funciona como contrasena: quien lo conozca
    // puede ver los avisos, asi que conviene que sea largo y al azar.
    'push' => [
        'modo' => 'ntfy',
        'servidor' => 'https://ntfy.sh',
        'token' => '',                    // solo si usas una cuenta de ntfy con clave
    ],

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
