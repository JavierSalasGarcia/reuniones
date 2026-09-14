# Avisos en el reloj

Este documento cubre la primera etapa: que tu reloj vibre y te muestre quién acaba de
formarse en la cola, sin instalar nada en el reloj. La segunda etapa, una aplicación
propia de Wear OS con la pantalla en vivo, va aparte.

## Tu reloj

Es un Galaxy Watch7 de 40 milímetros, modelo SM-L310, que corre Wear OS 5. Eso permite
las dos cosas: los avisos que se describen aquí, que no requieren instalar nada, y la
aplicación propia con la pantalla en vivo, que está en la carpeta `reloj` con sus
instrucciones en `reloj/LEEME.md`.

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

## La aplicación del reloj

La segunda etapa ya está escrita: una aplicación que se instala en el reloj y muestra en
vivo a quién atiendes con el tiempo corriendo, quién sigue y cuántos esperan, vibrando
cuando alguien se forma. Lleva su propia llave de solo lectura, distinta a la de la
laptop, para que con ella no se pueda llamar turnos ni cancelar nada. Las instrucciones
para compilarla e instalarla están en `reloj/LEEME.md`.
