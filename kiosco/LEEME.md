# Monitor de la entrada (Raspberry Pi)

La Raspberry no calcula nada: es una ventana. Arranca sola, abre el navegador a
pantalla completa en la vista de turnos y se queda ahí. Si se cae el internet cambia
al respaldo que sirve tu laptop en la red local, y regresa al sitio público en cuanto
vuelve la conexión. Fuera del horario de atención apaga el monitor.

## Lo que necesitas

Una Raspberry Pi 3, 4 o 5 con Raspberry Pi OS **con escritorio**, conectada al monitor
por HDMI y a la red de la facultad, con inicio de sesión automático activado
(`sudo raspi-config` → System Options → Boot / Auto Login → Desktop Autologin).

Tu laptop necesita dirección IP fija en esa misma red y el sitio local corriendo con
`scripts\servidor.cmd`. La primera vez, Windows preguntará si permite la conexión:
acepta en redes privadas, o crea la regla a mano para el puerto 8010.

## Instalación

En la Raspberry, con el usuario del escritorio y sin `sudo`:

```
git clone https://github.com/JavierSalasGarcia/reuniones.git
bash reuniones/kiosco/instalar.sh
```

Después edita `/etc/reuniones-kiosco.conf` con la clave de tu dependencia y la IP de
la laptop, y reinicia la pantalla:

```
sudo nano /etc/reuniones-kiosco.conf
systemctl --user restart reuniones-kiosco.service
```

## Cómo decide qué mostrar

Cada treinta segundos consulta `estado.json` del sitio público. Si responde, muestra
`https://fingenieria.mx/citas/sa/pantalla`; si no, muestra `http://IP-DE-TU-LAPTOP:8010/`,
que es la misma pantalla con la última fila que la laptop alcanzó a conocer, marcada
como «red local» para que se note que puede estar desfasada. El cambio se nota apenas
como un parpadeo del navegador.

Ese respaldo solo expone la pantalla de turnos. Los expedientes, las minutas y las
fotografías siguen atados a `localhost` en tu laptop y no se sirven a la red.

## Encendido y apagado del monitor

Un temporizador revisa cada cinco minutos el horario que publicaste desde la pestaña
Agenda y enciende o apaga la pantalla según corresponda, con veinte minutos de gracia
antes y después. Si no hay internet usa las horas fijas de la configuración. Funciona
con Wayland (`wlopm`), con X11 (`xset`) y con el control de HDMI de la Raspberry
(`vcgencmd`), en ese orden.

## Revisar qué está pasando

```
systemctl --user status reuniones-kiosco.service
journalctl --user -u reuniones-kiosco -f
bash ~/.local/bin/energia.sh --consultar     # 1 = debe estar encendida
```

Para salir del modo kiosco y usar el escritorio, `systemctl --user stop
reuniones-kiosco.service`; para volver, `start`.

## Monitor vertical

Si el monitor está de pie, gira la imagen en `sudo raspi-config` → Display Options →
Screen Rotation, o con `wlr-randr --output HDMI-A-1 --transform 90`. La vista se acomoda
sola: en pantallas angostas el turno actual queda arriba y la lista abajo.
