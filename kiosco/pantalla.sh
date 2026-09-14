#!/usr/bin/env bash
# Mantiene el navegador en pantalla completa mostrando los turnos.
# Si el sitio publico no responde, cambia al respaldo de la laptop en la red
# local, y regresa solo cuando vuelve el internet.
set -u

CONF="${REUNIONES_CONF:-/etc/reuniones-kiosco.conf}"
[ -r "$CONF" ] && . "$CONF"

URL_NUBE="${URL_NUBE:-}"
URL_PRUEBA="${URL_PRUEBA:-$URL_NUBE}"
URL_LOCAL="${URL_LOCAL:-}"
INTERVALO="${INTERVALO:-30}"

navegador() {
    for binario in chromium-browser chromium google-chrome; do
        command -v "$binario" >/dev/null 2>&1 && { echo "$binario"; return; }
    done
    echo ""
}

NAVEGADOR="$(navegador)"
if [ -z "$NAVEGADOR" ]; then
    echo "No encontre Chromium. Instalalo con: sudo apt install chromium-browser" >&2
    exit 1
fi

# Bajo X11 conviene apagar el protector de pantalla y esconder el puntero.
if [ -n "${DISPLAY:-}" ]; then
    xset s off -dpms 2>/dev/null || true
    command -v unclutter >/dev/null 2>&1 && (unclutter -idle 0 &) || true
fi

lanzar() {
    "$NAVEGADOR" \
        --kiosk "$1" \
        --ozone-platform-hint=auto \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-features=TranslateUI \
        --check-for-update-interval=31536000 \
        --autoplay-policy=no-user-gesture-required \
        --user-data-dir="$HOME/.cache/reuniones-kiosco" \
        >/dev/null 2>&1 &
}

hay_sitio() {
    [ -n "$URL_PRUEBA" ] && curl -sf --max-time 6 "$URL_PRUEBA" >/dev/null 2>&1
}

limpiar() {
    pkill -f "$NAVEGADOR" 2>/dev/null
    exit 0
}
trap limpiar TERM INT

actual=""
while true; do
    if hay_sitio; then
        destino="$URL_NUBE"
    else
        destino="${URL_LOCAL:-$URL_NUBE}"
    fi

    if [ "$destino" != "$actual" ] || ! pgrep -f "$NAVEGADOR" >/dev/null 2>&1; then
        pkill -f "$NAVEGADOR" 2>/dev/null
        sleep 1
        lanzar "$destino"
        actual="$destino"
        logger -t reuniones-kiosco "mostrando $destino" 2>/dev/null || true
    fi
    sleep "$INTERVALO"
done
