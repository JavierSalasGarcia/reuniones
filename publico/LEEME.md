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
`.htaccess` esté presente: ni los archivos que adjunta la gente ni las minutas deben
servirse por web; solo se bajan por la API con el token de la dependencia.

Si ya tenías la base creada de una instalación anterior, importa además
`migraciones/001_minutas.sql`, que agrega la tabla donde viven las minutas, y
`migraciones/002_jornadas.sql`, que agrega la de las jornadas diarias, y
`migraciones/003_push.sql`, que agrega el canal de avisos al celular, y
`migraciones/004_token_reloj.sql`, que agrega la llave de solo lectura del reloj.

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

## Correo y minutas

Todo el correo sale de aquí por SMTP con las credenciales del buzón de `fingenieria.mx`:
los códigos de verificación, los avisos de la fila y también las minutas. La laptop sube
el PDF de la minuta por la API, el servidor lo guarda en `subidas/minutas/<dependencia>/
<persona>/` y lo manda como adjunto. La transcripción original nunca sube.

Con `minutas_dias => 0` las minutas se conservan mientras exista el expediente; si pones
un número, las más viejas se borran solas cuando la laptop consulta el expediente.

El modo `mail`, que usa la función de PHP del hosting, queda como alternativa si el buzón
SMTP diera problemas.

## Pruebas

Desde la raíz del proyecto, sin necesidad de base de datos ni servidor:

```
php publico/pruebas/correr.php
```

Cubren el cálculo de horas de la fila, los colchones, los choques con reuniones,
el cierre del día, la verificación por correo y el freno contra abuso.
