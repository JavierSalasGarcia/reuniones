# Guía de instalación, configuración y pruebas

Todo el sistema en un solo documento, dispositivo por dispositivo. El orden importa:
primero el servidor, porque de ahí sale el token que necesita la laptop; después la
laptop, que es donde vive tu trabajo diario; al final la Raspberry, que solo muestra lo
que los otros dos ya producen.

Repositorio: `https://github.com/JavierSalasGarcia/reuniones`
Rama de trabajo: `claude/visitor-recognition-system-yo8nlr`

---

## Antes de empezar: datos que conviene tener a la mano

Del hosting de `fingenieria.mx` necesitas el nombre de la base de datos MySQL con su
usuario y contraseña, y las credenciales del buzón de correo `citas@fingenieria.mx`
con su servidor SMTP y su puerto. De la red de la facultad necesitas la dirección IP
fija de tu laptop, que es a donde apuntará la Raspberry cuando se caiga el internet.
Ten decidida también la contraseña del panel de administración del sitio público, y tu
correo institucional, que se usará como dirección de respuesta.

---

## 1. Servidor: `fingenieria.mx`

### Descarga y subida

Descarga el repositorio como ZIP desde GitHub, o clónalo si tienes acceso por SSH al
hosting. Lo único que se sube es el contenido de la carpeta `publico/`, que debe quedar
en `public_html/citas/`, de modo que `https://fingenieria.mx/citas/` sea la raíz del
sitio. No subas `reuniones/`, `kiosco/` ni `tests/`: esas carpetas no tienen nada que
hacer en el servidor.

Después de subir, la estructura en el hosting debe verse así:

```
public_html/citas/
├── index.php
├── api.php
├── admin.php
├── esquema.sql
├── .htaccess
├── lib/
├── vistas/
├── estatico/
├── migraciones/
└── subidas/            (con su .htaccess adentro)
```

### Base de datos

En cPanel crea una base MySQL y un usuario con todos los permisos sobre ella. Entra a
phpMyAdmin, selecciona la base e importa `esquema.sql`. Ese archivo ya incluye la tabla
de minutas; si alguna vez actualizas desde una versión anterior que no la tenía, importa
además `migraciones/001_minutas.sql`.

### Configuración

Copia `config.example.php` a `config.php` en la misma carpeta y edítalo. Los datos de la
base van en `db`; la dirección pública en `sitio` y `base_url`; el buzón de correo en
`correo`, con `modo` en `smtp`. En `responder_a` pon tu correo institucional para que,
aunque el mensaje salga de la facultad, las respuestas te lleguen a ti.

La contraseña del panel no se escribe en claro. Genera su huella y pégala en
`admin_hash`:

```
php -r "echo password_hash('la contraseña que elegiste', PASSWORD_DEFAULT);"
```

Si tu hosting no da acceso a PHP por línea de comandos, sube un archivo temporal con ese
mismo `echo`, ábrelo en el navegador, copia el resultado y bórralo enseguida.

### Permisos

La carpeta `subidas/` debe poder escribirse, con permisos 750 o 770, y su `.htaccess`
debe estar presente; ahí van los archivos que adjunta la gente y las minutas, y ninguno
de los dos debe servirse por web. Verifica que `config.php` no sea legible desde fuera
abriendo `https://fingenieria.mx/citas/config.php` en el navegador: debe negarse o
salir en blanco, nunca mostrar texto.

### Alta de tu dependencia

Entra a `https://fingenieria.mx/citas/admin`, escribe la contraseña y crea la
dependencia con clave `sa`, nombre «Subdirección Académica», tu nombre como titular y
`uaemex.mx` como dominio aceptado. Al guardar aparece un token largo que se muestra una
sola vez: cópialo ahora, va en el archivo `.env` de la laptop. Si lo pierdes, se
regenera desde el mismo panel, pero el anterior deja de servir.

El día que se sume dirección, es otra dependencia con clave `dir` creada desde este
mismo panel, con su propio token. No se toca nada más.

### Pruebas del servidor

Si tienes PHP por línea de comandos, desde la carpeta del proyecto completo:

```
php publico/pruebas/correr.php
```

Debe responder «123 comprobaciones correctas». Esas pruebas no tocan tu base de datos
real ni mandan correos; usan una base en memoria.

En el navegador, comprueba que `https://fingenieria.mx/citas/sa` muestra el formulario
para tomar turno, que `https://fingenieria.mx/citas/sa/fila` abre la fila del día y que
`https://fingenieria.mx/citas/sa/estado.json` devuelve un texto que empieza con
`{"ahora":`. Comprueba también que `https://fingenieria.mx/citas/api?d=sa&accion=estado`
responde `{"error":"no autorizado"}`: eso confirma que la API está protegida.

---

## 2. Laptop con Windows

### Descarga

Instala Python 3.11 o más reciente desde `python.org`, marcando la casilla «Add Python
to PATH» durante la instalación. Instala también Git desde `git-scm.com` si quieres
poder actualizar con un comando. Después, en PowerShell:

```
cd C:\
git clone https://github.com/JavierSalasGarcia/reuniones.git
cd reuniones
git checkout claude/visitor-recognition-system-yo8nlr
```

Si prefieres no usar Git, descarga el ZIP desde GitHub y descomprímelo en `C:\reuniones`.

### Instalación

```
powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
```

El script crea el entorno virtual, instala las dependencias, y copia
`config.example.toml` a `config.toml` y `.env.example` a `.env`. Tarda varios minutos
porque descarga las librerías de visión.

### Configuración

Abre `config.toml` con el Bloc de notas. En `[general]` revisa `carpeta_datos`, que por
omisión es `C:/Reuniones` y conviene que esté en un disco cifrado con BitLocker. En
`[camara]` deja `indice` en 0 para la cámara integrada, o ponlo en 1 si usarás una
cámara USB externa. En `[correo]` deja `via = "servidor"` y pon tu correo institucional
en `responder_a`. En `[nube]` confirma la dirección `https://fingenieria.mx/citas` y la
clave `sa`.

Abre `.env` y pega en `REUNIONES_NUBE_TOKEN` el token que te dio el panel del servidor.
`REUNIONES_SMTP_PASSWORD` solo hace falta si algún día cambias a `via = "laptop"`.
`GEMINI_API_KEY` es opcional y solo sirve para que la búsqueda redacte respuestas.

### Primer arranque

```
scripts\servidor.cmd
```

Abre el navegador en `http://localhost:8000`. La primera identificación descarga los
modelos de reconocimiento facial, unos trescientos megas por única vez, así que hazla
con internet disponible. Para que el sistema esté siempre listo, crea un acceso directo
a `scripts\servidor.cmd` y colócalo en la carpeta de inicio de Windows, que se abre con
`Win+R` y el comando `shell:startup`.

### Permiso de red

La primera vez que arranque, Windows preguntará si permite la conexión: acepta en redes
privadas. Eso abre el puerto 8010, que es por donde la Raspberry consulta el respaldo de
la pantalla. El sitio de expedientes sigue solo en `localhost` y no se expone a la red.

### Pruebas de la laptop

Las pruebas automáticas no necesitan cámara ni internet:

```
.venv\Scripts\python.exe -m pytest
```

Debe responder «96 passed». Después, las pruebas a mano. Con el servidor corriendo,
verifica el estado general:

```
scripts\reunion.cmd estado
```

Prueba la cámara dando de alta a alguien de confianza, o a ti mismo:

```
scripts\reunion.cmd nueva "Nombre De Prueba" prueba@uaemex.mx
```

Debe grabar seis segundos, abrir el expediente en el navegador y mostrar una fotografía
tipo credencial con gesto neutro. Si la foto no te convence, en la misma ficha hay dos
alternativas del mismo video. Enseguida cierra el navegador, vuelve a ponerte frente a
la cámara y corre `scripts\reunion.cmd`: debe reconocerte y abrir tu expediente.

Prueba la ingesta de transcripciones creando dos archivos de texto cualquiera en
`C:\Reuniones\transcripciones` con los nombres del día y hora de esa reunión de prueba,
por ejemplo `20260914_1035_original.txt` y `20260914_1035_minuta.txt`. En segundos deben
desaparecer de esa carpeta y aparecer dentro de la reunión en el navegador. Si no se
asocian solos, quedan en la pestaña Bandeja para asignarlos con un clic, que también
conviene probar.

Prueba el correo desde la reunión, con el botón de enviar la minuta a tu propia cuenta
institucional. Debe llegar con el PDF adjunto y con remitente de `fingenieria.mx`. En la
ficha de la persona, el enlace «Minutas en el servidor» debe mostrar esa misma minuta
guardada allá.

Al terminar, borra la persona de prueba junto con su carpeta en
`C:\Reuniones\expedientes`, o consérvala mientras aprendes el sistema.

---

## 3. Raspberry Pi del monitor

### Preparación de la tarjeta

Graba Raspberry Pi OS **con escritorio** en la microSD usando Raspberry Pi Imager. En las
opciones avanzadas del propio Imager conviene configurar desde ahí el nombre de usuario,
la red y el acceso remoto por SSH. Conecta la Pi al monitor por HDMI y a la red de la
facultad, y activa el inicio de sesión automático con `sudo raspi-config`, en System
Options y luego Boot / Auto Login, eligiendo Desktop Autologin.

### Descarga e instalación

Con el usuario del escritorio, sin `sudo`:

```
git clone https://github.com/JavierSalasGarcia/reuniones.git
cd reuniones
git checkout claude/visitor-recognition-system-yo8nlr
bash kiosco/instalar.sh
```

El script instala Chromium y las utilerías necesarias, copia los guiones a
`~/.local/bin`, crea `/etc/reuniones-kiosco.conf` y deja activos los servicios que
arrancan la pantalla al encender y revisan cada cinco minutos si el monitor debe estar
prendido.

### Configuración

```
sudo nano /etc/reuniones-kiosco.conf
```

Ahí van la dirección de tu dependencia en `URL_NUBE` y `URL_PRUEBA`, y en `URL_LOCAL` la
dirección IP fija de tu laptop con el puerto 8010, por ejemplo
`http://192.168.1.50:8010/`. Guarda y reinicia la pantalla:

```
systemctl --user restart reuniones-kiosco.service
```

### Pruebas de la Raspberry

El monitor debe mostrar la pantalla de turnos a pantalla completa, con el código QR
visible. Escanea ese QR con tu celular: debe abrir la página para tomar turno.

Para probar el respaldo, desconecta la Raspberry del internet dejándola en la red local,
o apaga el módem un momento. En menos de un minuto la pantalla debe cambiar al respaldo
de la laptop, reconocible porque abajo dice «red local». Al volver la conexión, regresa
sola al sitio público.

Para probar el encendido automático:

```
bash ~/.local/bin/energia.sh --consultar
```

Responde `1` si según el horario publicado el monitor debe estar encendido y `0` si no.
Cambia temporalmente tu horario desde la pestaña Agenda de la laptop y vuelve a
consultarlo para ver que responde distinto.

Si algo no arranca:

```
systemctl --user status reuniones-kiosco.service
journalctl --user -u reuniones-kiosco -f
```

Para salir del modo kiosco y usar el escritorio, `systemctl --user stop
reuniones-kiosco.service`; para volver, `start`.

---

## 4. Prueba de aceptación, con los tres dispositivos encendidos

Esta es la prueba que confirma que el sistema completo funciona.

Desde la laptop, en la pestaña Agenda, publica tu horario de la semana y aparta un rato
de media hora dentro del horario de hoy, con cualquier motivo. En la pestaña Fila,
marca la casilla de disponible.

Desde tu celular, escanea el QR del monitor, pide un turno de cinco minutos con un
asunto cualquiera, y confirma con el código que llega a tu correo institucional. La
página debe mostrarte tu número y una hora aproximada, y esa hora debe respetar el rato
que apartaste, es decir, si tu turno cayera dentro de la reunión o en los diez minutos
previos, debe recorrerse al terminar.

En la laptop, la pestaña Fila debe mostrar ese turno con su asunto y su hora. Pulsa
Llamar: el monitor de la entrada debe cambiar en segundos al turno actual con el nombre,
y en la laptop debe abrirse el expediente de esa persona con la reunión ya creada. Si
usaste un correo que no existe en tus expedientes, el sistema te lleva al alta con los
datos ya escritos.

Desde el celular, entra al enlace que te llegó por correo y cancela el turno, para
comprobar que la fila se recalcula.

Por último, suelta en la carpeta de transcripciones los dos archivos de texto de esa
reunión, espera a que se asocien, y envía la minuta a tu correo institucional. Debe
llegar con el PDF adjunto.

---

## Mantenimiento

El video del alta se borra solo a los siete días; `scripts\reunion.cmd limpiar` lo
fuerza cuando quieras. El índice de búsqueda se reconstruye con
`scripts\reunion.cmd indexar` si alguna vez notas que falta algo. El estado general del
sistema, incluida la configuración del correo, se revisa con
`scripts\reunion.cmd estado` o desde la pestaña Ajustes.

Para actualizar cualquiera de los tres dispositivos a una versión nueva, en la laptop y
en la Raspberry basta `git pull` seguido del script de instalación correspondiente; en
el servidor, volver a subir el contenido de `publico/` conservando tu `config.php` y la
carpeta `subidas/`.

Respalda con regularidad la carpeta `C:\Reuniones` completa, que es donde viven los
expedientes, las fotografías, las minutas y la base de datos. Lo del servidor es una
copia de trabajo; lo de la laptop es el original.

---

## Problemas frecuentes

Si la cámara no abre, revisa que ninguna otra aplicación la esté usando y que Windows
permita el acceso a la cámara para aplicaciones de escritorio; si usas una cámara USB,
prueba con `indice = 1` en `config.toml`.

Si el reconocimiento falla seguido con la misma persona, ábrela desde Personas y vuelve
a tomarle la fotografía desde su ficha; el sistema aprende de cada visita y mejora solo,
pero un retrato con mala luz lo estorba todo.

Si los correos no llegan, revisa que en el servidor `modo` esté en `smtp` y que las
credenciales del buzón sean correctas; `scripts\reunion.cmd probar-correo` te dice si la
laptop alcanza al servidor.

Si la pestaña Fila dice que falta el token, es que `.env` no tiene
`REUNIONES_NUBE_TOKEN`, o que el token se regeneró en el panel y quedó el viejo.

Si un envío queda como pendiente, no hay nada que hacer: significa que no había conexión
y saldrá solo en cuanto vuelva.
