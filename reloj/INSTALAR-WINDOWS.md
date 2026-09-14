# Instalar la aplicación del reloj, paso a paso

Escrito para quien nunca ha compilado una aplicación de Android. Son unas dos horas la
primera vez, casi todas de espera mientras se descargan cosas. Después, reinstalar es
cuestión de dos minutos.

## Qué vas a instalar y por qué

**Android Studio** es el programa con el que se arma la aplicación. Trae adentro todo lo
demás, así que es lo único que descargas a mano. Dentro de él vienen el **SDK de
Android**, que son las piezas del sistema contra las que se compila; **Gradle**, que es
el armador que junta el código y produce el archivo instalable; y **adb**, que es el
puente por el que tu computadora le pasa la aplicación al reloj. No necesitas instalar
Java por separado: Android Studio trae el suyo.

Necesitas unos diez gigas libres en disco y una conexión decente, porque la primera vez
se descargan alrededor de cinco.

## 1. Descargar Android Studio

Entra a `https://developer.android.com/studio`, pulsa el botón de descarga para Windows,
acepta los términos y guarda el instalador, que pesa cerca de un giga.

Ejecuta el instalador y acepta las opciones que propone, sin cambiar nada. Cuando
termine, ábrelo.

La primera vez aparece un asistente de bienvenida. Elige la instalación **Standard**,
acepta las licencias que muestre y deja que descargue. Esta es la parte larga: entre diez
y treinta minutos según tu internet. No cierres la ventana.

## 2. Abrir el proyecto

En la pantalla de bienvenida de Android Studio pulsa **Open**. Navega hasta la carpeta
del proyecto y selecciona precisamente la carpeta `reloj`, no la carpeta que la contiene.
Si clonaste el repositorio en `C:\reuniones`, entonces es `C:\reuniones\reloj`. Pulsa OK.

Android Studio abrirá el proyecto y empezará solo lo que llama **Gradle sync**, que es
descargar las bibliotecas que la aplicación usa. Abajo verás una barra de progreso. La
primera vez tarda entre cinco y quince minutos.

Si aparece un aviso amarillo arriba diciendo que falta algún componente del SDK, con un
enlace que dice *Install missing SDK package* o similar, haz clic en ese enlace y acepta.
Vuelve a esperar a que termine.

Sabrás que todo va bien cuando abajo diga *BUILD SUCCESSFUL* o *Sync finished* y no haya
letras rojas.

## 3. Poner la llave del reloj

En tu navegador entra al panel de administración del sitio, en
`https://fingenieria.mx/citas/admin`, busca tu dependencia y pulsa **Generar llave del
reloj**. Copia la cadena que aparece; solo se muestra una vez.

En el explorador de archivos de Windows, entra a `C:\reuniones\reloj`, copia el archivo
`local.properties.example` y pégalo ahí mismo. Renombra la copia como `local.properties`,
exactamente así, sin el `.example`. Ábrelo con el Bloc de notas y déjalo así, con tu llave
pegada después del signo igual:

```
fila.sitio=https://fingenieria.mx/citas
fila.dependencia=sa
fila.token=aquipegaslallavequecopiaste
```

Guarda y cierra. Si Windows te oculta las extensiones y no sabes si quedó bien nombrado,
en el explorador activa *Ver → Extensiones de nombre de archivo* y comprueba que diga
`local.properties` y no `local.properties.txt`.

De vuelta en Android Studio, pulsa el elefante de **Sync Project with Gradle Files**, en
la barra de herramientas, o el aviso que aparezca arriba, para que tome el archivo nuevo.

## 4. Preparar el reloj

En el reloj entra a **Ajustes**, baja hasta **Acerca del reloj**, entra a **Información de
software** y toca cinco veces seguidas sobre el número de versión, hasta que aparezca un
mensaje diciendo que ya eres desarrollador.

Regresa a Ajustes, entra a **Opciones de desarrollador**, que ahora aparece al final, y
activa **Depuración ADB** y **Depuración inalámbrica**.

Asegúrate también de que el reloj esté conectado a la misma red Wi‑Fi que tu computadora:
en Ajustes, Conexiones, Wi‑Fi, conéctalo a la red de tu oficina. Este paso es el que más
se olvida y sin él la computadora no encuentra el reloj.

## 5. Emparejar el reloj con la computadora

En el reloj, dentro de Opciones de desarrollador, entra a **Depuración inalámbrica** y
elige **Vincular nuevo dispositivo**. La pantalla mostrará un código de seis dígitos y una
dirección con dos puntos y un número, algo como `192.168.1.77:41235`. Déjala encendida.

En Android Studio, abre el **Device Manager**, que es el ícono de un celular en la barra
lateral derecha. En su menú, elige **Pair Devices Using Wi‑Fi**. Se abre una ventana con
la opción **Pair using pairing code**. Ahí aparecerá tu reloj en la lista; selecciónalo y
escribe el código de seis dígitos que muestra la pantalla del reloj.

Si Windows pregunta si permites que adb use la red, dile que sí, en redes privadas.

Cuando empareje, el reloj aparece en la lista de dispositivos de Android Studio, arriba,
junto al botón de ejecutar.

## 6. Instalar la aplicación

Arriba, en la barra de herramientas, revisa que el selector de dispositivo muestre tu
reloj y que junto diga **app**. Pulsa el triángulo verde de **Run**.

La primera compilación tarda unos minutos. Cuando termine, la aplicación se abre sola en
el reloj. Si te pide confirmar la instalación en la pantalla del reloj, acepta.

A partir de ahí la encuentras en la lista de aplicaciones del reloj con el nombre
**Fila**.

## 7. Agregar el mosaico

El mosaico es la tarjeta que se ve deslizando el dedo hacia la izquierda desde la
carátula. Para agregarlo, mantén el dedo presionado sobre la carátula del reloj hasta que
entre en modo de edición, desliza hacia la izquierda hasta el final de las tarjetas, toca
el botón con el signo de más y busca **Fila** en la lista. Tócalo y listo.

Desde ese momento, un deslizón desde la carátula te muestra a quién estás atendiendo con
los minutos que le faltan, quién sigue y cuántos esperan. Tocando la tarjeta se abre la
aplicación completa.

También se puede agregar desde el celular, en Galaxy Wearable, en la sección de mosaicos.

## Si algo sale mal

Si el reloj no aparece al emparejar, casi siempre es el Wi‑Fi: comprueba que el reloj esté
en la misma red que la computadora y que la pantalla de vinculación siga abierta, porque
el código caduca al salir.

Si Android Studio marca en rojo algo sobre versiones de Gradle o del plugin, acepta el
asistente de actualización que el propio programa ofrece, y si insiste, mándame el texto
del error tal cual y te digo qué línea cambiar.

Si la aplicación abre pero dice que la llave no es válida, es que la del `local.properties`
no coincide con la del panel; genera una nueva allá, actualiza el archivo, sincroniza y
vuelve a pulsar Run.

Si dice que no hay conexión con el sitio, el reloj no está alcanzando internet. Con el
celular cerca se resuelve solo; también funciona si el reloj está en una red Wi‑Fi con
salida a internet.

## Para reinstalar después

No hay que repetir nada de esto. Basta con que el reloj tenga la depuración inalámbrica
encendida y esté en la misma red, conectarlo desde el Device Manager y pulsar Run.
