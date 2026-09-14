#!/usr/bin/env bash
# Instalacion del kiosco en la Raspberry Pi.  Ejecutar como el usuario del
# escritorio (normalmente "pi"), no con sudo:
#     bash kiosco/instalar.sh
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="/etc/reuniones-kiosco.conf"

echo "Instalando paquetes necesarios…"
sudo apt-get update -qq
sudo apt-get install -y chromium-browser unclutter curl python3 || \
    sudo apt-get install -y chromium unclutter curl python3

echo "Copiando los guiones a ~/.local/bin…"
mkdir -p "$HOME/.local/bin"
install -m 755 "$AQUI/pantalla.sh" "$HOME/.local/bin/pantalla.sh"
install -m 755 "$AQUI/energia.sh" "$HOME/.local/bin/energia.sh"

if [ ! -f "$CONF" ]; then
    echo "Creando $CONF (edítalo con la clave de tu dependencia y la IP de la laptop)."
    sudo install -m 644 "$AQUI/kiosco.conf.example" "$CONF"
else
    echo "$CONF ya existe; no lo toco."
fi

echo "Instalando los servicios de usuario…"
mkdir -p "$HOME/.config/systemd/user"
install -m 644 "$AQUI/systemd/reuniones-kiosco.service" "$HOME/.config/systemd/user/"
install -m 644 "$AQUI/systemd/reuniones-energia.service" "$HOME/.config/systemd/user/"
install -m 644 "$AQUI/systemd/reuniones-energia.timer" "$HOME/.config/systemd/user/"

systemctl --user daemon-reload
systemctl --user enable --now reuniones-kiosco.service
systemctl --user enable --now reuniones-energia.timer
sudo loginctl enable-linger "$USER" >/dev/null 2>&1 || true

cat <<'FIN'

Listo.

  Edita /etc/reuniones-kiosco.conf con la dirección de tu dependencia y la IP
  de la laptop, y después reinicia la pantalla con:

      systemctl --user restart reuniones-kiosco.service

  Para ver qué está haciendo:

      journalctl --user -u reuniones-kiosco -f

FIN
