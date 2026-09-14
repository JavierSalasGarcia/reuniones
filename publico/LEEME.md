# Parte pública: turnos y citas

Esta carpeta se sube al hosting compartido. Es la única pieza que vive fuera de tu
laptop, y solo guarda turnos, citas y tu disponibilidad: ni expedientes, ni minutas,
ni fotografías.

## Instalación en cPanel

Sube el contenido de `publico/` a `public_html/citas/`, de modo que la dirección
`https://fingenieria.mx/citas/sa` funcione. Después:

Crea una base de datos MySQL y un usuario con permisos sobre ella, e importa
`esquema.sql` desde phpMyAdmin.

Copia `config.example.php` a `config.php` y llena los datos de la base, la dirección
del sitio y el buzón de correo desde el que saldrán los códigos de verificación.
Ese buzón es del hosting, no el institucional: la minuta se sigue enviando desde tu
laptop con tu cuenta de la UAEM.

Genera la contraseña del panel de administración y pégala en `admin_hash`:

```
php -r "echo password_hash('la contraseña que quieras', PASSWORD_DEFAULT);"
```

Asegúrate de que `subidas/` tenga permisos de escritura (750 o 770) y de que su
`.htaccess` esté presente: los archivos que adjunta la gente no deben servirse por web,
solo bajarlos tu laptop a través de la API.

Si tu hosting no tiene `mod_rewrite`, todo sigue funcionando con la forma larga de las
direcciones: `https://fingenieria.mx/citas/index.php?r=sa`.

## Alta de la dependencia

Entra a `https://fingenieria.mx/citas/admin`, crea la dependencia con la clave `sa`
(el día que se sume dirección será otra con la clave `dir`, sin tocar nada más) y copia
el token que se muestra una sola vez. Ese token va en el archivo `.env` de tu laptop
como `REUNIONES_NUBE_TOKEN`.

En la laptop, `config.toml` necesita la sección `[nube]` con la dirección del sitio y la
clave de tu dependencia. Desde ahí publicas horarios, marcas disponible o no disponible
y atiendes la fila.

## Direcciones

`/citas/sa` es donde llega quien escanea el QR: toma turno de 5 o 10 minutos, o pide
una reunión más larga con descripción y archivos. `/citas/sa/fila` es la fila en vivo
para el celular. `/citas/sa/pantalla` es la vista de pantalla completa para el monitor
de la entrada. `/citas/admin` es el panel de dependencias.

## Correo

El modo `mail` usa la función de PHP del hosting y suele bastar. Si los correos no
llegan a las cuentas de la UAEM, cambia a modo `smtp` y pon las credenciales del buzón
de `fingenieria.mx`; el sistema habla SMTP directo con STARTTLS.

## Pruebas

Desde la raíz del proyecto, sin necesidad de base de datos ni servidor:

```
php publico/pruebas/correr.php
```

Cubren el cálculo de horas de la fila, los colchones, los choques con reuniones,
el cierre del día, la verificación por correo y el freno contra abuso.
