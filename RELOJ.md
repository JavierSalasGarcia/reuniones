# Avisos en el reloj

Este documento cubre la primera etapa: que tu reloj vibre y te muestre quién acaba de
formarse en la cola, sin instalar nada en el reloj. La segunda etapa, una aplicación
propia de Wear OS con la pantalla en vivo, va aparte.

## Primero, el modelo de tu reloj

En el reloj, entra a Ajustes, baja hasta «Acerca del reloj» y anota el nombre y el número
de modelo, que empieza con `SM-`. Desde el celular también lo ves abriendo Galaxy
Wearable, en Ajustes del reloj y luego Acerca del reloj. Ese número decide si tu reloj
corre Wear OS, donde sí se pueden instalar aplicaciones propias, o el viejo Tizen de los
modelos anteriores, donde el camino es distinto. Para lo de esta primera etapa da igual
cuál sea: funciona en los dos, porque el reloj solo repite lo que llega al celular.

## Cómo funciona

Cuando alguien toma turno, el servidor de `fingenieria.mx` publica un aviso en un canal
privado. Tu celular, que está suscrito a ese canal, muestra la notificación, y el reloj
la repite vibrando en tu muñeca con el texto completo: «Turno 3 · Ana Ruiz» y debajo
«Revalidación · 10 min · le tocaría 11:20». Al tocarlo se abre la fila en el navegador.

## Instalación

En el celular, instala la aplicación **ntfy** desde Google Play. Ábrela, pulsa el botón
de suscribirse a un tema y escribe exactamente el tema que aparece en el panel de
administración del sitio, en la ficha de tu dependencia, en el campo «Tema de avisos al
celular». Es una cadena larga, algo como `sa-9f3c1a7b2d4e6f80`.

En el servidor, revisa que `config.php` tenga el bloque `push` con `'modo' => 'ntfy'`.
Si el campo del tema está vacío en el panel, escribe uno tú mismo: que sea largo y
difícil de adivinar, porque cualquiera que lo conozca podría ver tus avisos.

En el reloj, comprueba que las notificaciones del celular se repiten: en Galaxy Wearable,
entra a Notificaciones, activa el interruptor general y asegúrate de que ntfy aparezca
permitida en la lista de aplicaciones.

## Prueba

Desde cualquier terminal con internet:

```
curl -d "Prueba desde el servidor" -H "Title: Turno 9 - Prueba" https://ntfy.sh/TU-TEMA
```

El celular debe sonar y el reloj vibrar en un par de segundos. Después haz la prueba de
verdad: toma un turno desde otro teléfono con el QR y comprueba que el aviso llega con el
nombre y la hora estimada.

## Privacidad

El aviso viaja por un servicio de terceros, así que el nombre y el asunto de la persona
salen de tus servidores. Si prefieres que no, en el panel de administración desmarca
«Incluir nombre y asunto en el aviso» y entonces el reloj solo dirá «Nuevo turno 3» con
la duración y la hora; para saber de quién se trata miras la fila en tu laptop. Si algún
día quieres que ni eso salga, ntfy se puede instalar en el propio hosting.

## Qué falta

La segunda etapa es una aplicación instalada en el reloj, con una pantalla y un mosaico
que muestren en vivo quién sigue y cuánto lleva la reunión actual, sin depender de que
te llegue una notificación. Esa parte necesita que compiles el proyecto en tu laptop con
Android Studio y que actives el modo desarrollador del reloj, y el primer paso es que me
digas el número de modelo.
