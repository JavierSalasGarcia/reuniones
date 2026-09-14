# Fila · aplicación para el Galaxy Watch7

Muestra en la muñeca a quién estás atendiendo y cuánto le falta, quién sigue y a qué
hora le tocaría, y vibra cuando alguien nuevo se forma o cuando la reunión en curso se
pasa del tiempo. Consulta el sitio de `fingenieria.mx` cada veinte segundos mientras la
tienes a la vista, y no hace nada más: la llave que lleva dentro es de solo lectura.

Probado contra el servidor real por el lado de los datos; **el proyecto en sí no se
compiló en el equipo donde se escribió**, porque ahí no hay SDK de Android. Si la
primera compilación marca algo, mándame el error tal cual y lo corrijo.

## Lo que necesitas

Android Studio reciente en tu laptop, con el SDK de Android 35 instalado, que el propio
Android Studio ofrece descargar la primera vez. El reloj y la laptop deben estar en la
misma red Wi-Fi para la instalación; después, la aplicación funciona con la conexión del
reloj o con la del celular emparejado.

## Antes de compilar

En el panel de administración del sitio, en tu dependencia, pulsa «Generar llave del
reloj» y copia lo que aparece: se muestra una sola vez y no es la misma llave que usa la
laptop. Con esa llave solo se puede mirar; no sirve para llamar turnos ni cancelar nada,
así que si algún día pierdes el reloj basta con regenerarla.

Copia `local.properties.example` a `local.properties` y llénalo:

```
fila.sitio=https://fingenieria.mx/citas
fila.dependencia=sa
fila.token=la-llave-que-copiaste
```

Ese archivo no se sube al repositorio. Android Studio le agregará solo la línea `sdk.dir`
la primera vez que abra el proyecto.

## Modo desarrollador en el reloj

En el reloj entra a Ajustes, luego Acerca del reloj e Información de software, y toca
cinco veces seguidas sobre el número de versión hasta que avise que ya eres
desarrollador. Regresa a Ajustes, entra a Opciones de desarrollador y activa «Depuración
ADB» y «Depuración inalámbrica».

## Instalación

Dentro de Opciones de desarrollador, entra a Depuración inalámbrica y elige «Vincular
nuevo dispositivo». El reloj mostrará una dirección con puerto y un código de seis
dígitos. En la laptop, desde la carpeta `platform-tools` del SDK:

```
adb pair 192.168.1.77:41234
```

Escribe el código cuando lo pida. Después conéctate al puerto que muestra la pantalla
principal de depuración inalámbrica, que es distinto al de vinculación:

```
adb connect 192.168.1.77:5555
```

Abre la carpeta `reloj` con Android Studio, espera a que sincronice, elige el reloj en la
lista de dispositivos y pulsa Run. La aplicación queda instalada como **Fila** en la
lista de aplicaciones del reloj.

## Qué vas a ver

Arriba, el nombre de quien está adentro y en grande cuánto le falta, en verde mientras
alcance el tiempo y en rojo cuando ya se pasó, con el detalle de cuántos minutos lleva de
los que pidió. Abajo, quién sigue con su asunto y su hora aproximada, y cuántas personas
hay en fila. Si no estás atendiendo a nadie, arriba aparece la misma leyenda que ve la
gente: «Disponible hasta 12:00», «No disponible hasta 14:00» o el motivo del cierre.

El reloj vibra dos veces cortas cuando alguien nuevo se forma, y una vez larga la primera
vez que la reunión en curso se pasa del tiempo.

## Si algo falla

Un mensaje de llave inválida significa que la del `local.properties` ya no coincide con
la del panel; regenérala allá, actualiza el archivo y vuelve a instalar.

«Sin conexión con el sitio» aparece cuando el reloj no alcanza internet; con el celular
cerca se resuelve solo, y la pantalla conserva lo último que supo.

Si Gradle se queja de que falta el wrapper, compila desde el botón Run de Android Studio,
que usa su propia distribución. Si se queja de versiones, acepta el asistente de
actualización que ofrece el propio Android Studio.

## Lo que falta

Un mosaico, de esos que se ven deslizando desde la carátula sin abrir la aplicación,
para no tener que entrar. Se puede agregar encima de esto una vez que la aplicación
compile y la estés usando.
