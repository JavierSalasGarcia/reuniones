#!/usr/bin/env bash
# Prende y apaga el monitor segun el horario de atencion publicado.
# Se ejecuta cada cinco minutos desde el temporizador de systemd.
set -u

CONF="${REUNIONES_CONF:-/etc/reuniones-kiosco.conf}"
[ -r "$CONF" ] && . "$CONF"

URL_PRUEBA="${URL_PRUEBA:-}"
HORA_ENCENDIDO="${HORA_ENCENDIDO:-07:30}"
HORA_APAGADO="${HORA_APAGADO:-20:00}"
MARGEN="${MARGEN:-20}"

# Devuelve "1" si toca tener la pantalla encendida.
toca_encendida() {
    local json
    json="$(curl -sf --max-time 6 "$URL_PRUEBA" 2>/dev/null)"
    MARGEN="$MARGEN" HORA_ENCENDIDO="$HORA_ENCENDIDO" HORA_APAGADO="$HORA_APAGADO" \
    python3 - "$json" <<'PY'
import json
import os
import sys
from datetime import datetime, timedelta

margen = timedelta(minutes=int(os.environ.get("MARGEN", "20")))
ahora = datetime.now()


def entre(inicio: str, fin: str) -> bool:
    try:
        desde = datetime.combine(ahora.date(), datetime.strptime(inicio, "%H:%M").time()) - margen
        hasta = datetime.combine(ahora.date(), datetime.strptime(fin, "%H:%M").time()) + margen
    except ValueError:
        return False
    if hasta <= desde:
        # La ventana cruza la medianoche: se estira hacia el lado que toca.
        if ahora >= desde:
            hasta += timedelta(days=1)
        else:
            desde -= timedelta(days=1)
    return desde <= ahora <= hasta


crudo = sys.argv[1] if len(sys.argv) > 1 else ""
horarios = []
try:
    horarios = json.loads(crudo).get("horarios", []) if crudo else []
except json.JSONDecodeError:
    horarios = []

if horarios:
    # El horario que publica la oficina manda sobre las horas fijas.
    hoy = ahora.isoweekday()
    encendida = any(entre(h.get("inicio", ""), h.get("fin", ""))
                    for h in horarios if int(h.get("dia", 0)) == hoy)
else:
    encendida = entre(os.environ.get("HORA_ENCENDIDO", "07:30"),
                      os.environ.get("HORA_APAGADO", "20:00"))

print("1" if encendida else "0")
PY
}

encender() {
    wlopm --on '*' 2>/dev/null && return 0
    [ -n "${DISPLAY:-}" ] && xset dpms force on 2>/dev/null && return 0
    vcgencmd display_power 1 >/dev/null 2>&1
}

apagar() {
    wlopm --off '*' 2>/dev/null && return 0
    [ -n "${DISPLAY:-}" ] && xset dpms force off 2>/dev/null && return 0
    vcgencmd display_power 0 >/dev/null 2>&1
}

DECISION="$(toca_encendida)"

# Con --consultar solo dice que haria; sirve para probarlo sin tocar la pantalla.
if [ "${1:-}" = "--consultar" ]; then
    echo "$DECISION"
    exit 0
fi

if [ "$DECISION" = "1" ]; then
    encender
else
    apagar
fi
