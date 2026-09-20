#!/usr/bin/env bash
# ! scripts/install_docker.sh — ставит docker engine + compose plugin, вызывается из install.sh

SUDO="$( [ "$(id -u)" = 0 ] && echo '' || echo sudo )"

# семейство пакетов, чтобы знать чем ставить
detect_pkg_family() {
  PKG_FAM=''
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in
      *debian*|*ubuntu*) PKG_FAM=apt ;;
      *rhel*|*centos*|*fedora*|*almalinux*|*rocky*|*oracle*) PKG_FAM=dnf ;;
      *alpine*) PKG_FAM=apk ;;
    esac
  fi
  [ -n "$PKG_FAM" ] || PKG_FAM=unknown
}

install_docker_engine() {
  detect_pkg_family
  if command -v docker >/dev/null 2>&1; then
    ok "docker уже установлен: $(docker --version 2>/dev/null)"
  else
    info "docker не найден, ставлю (пакетный менеджер: $PKG_FAM, может занять минуту)"
    case "$PKG_FAM" in
      apt)
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq ca-certificates curl gnupg openssl
        $SUDO install -m 0755 -d /etc/apt/keyrings
        DISTRO_ID="$(. /etc/os-release; echo "$ID")"
        curl -fsSL "https://download.docker.com/linux/$DISTRO_ID/gpg" \
          | $SUDO gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
        $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
        ARCH="$(dpkg --print-architecture)"
        CODENAME="$(. /etc/os-release; echo "${VERSION_CODENAME:-$(lsb_release -cs 2>/dev/null || echo stable)}")"
        echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO_ID $CODENAME stable" \
          | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
          docker-buildx-plugin docker-compose-plugin
        ;;
      dnf)
        $SUDO dnf -y install dnf-plugins-core ca-certificates curl openssl >/dev/null
        $SUDO dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo >/dev/null 2>&1 \
          || $SUDO dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/centos/docker-ce.repo >/dev/null 2>&1 || true
        $SUDO dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        ;;
      apk)
        $SUDO apk add --no-cache docker docker-cli-compose openssl
        ;;
      *)
        warn "дистрибутив не распознал — пробую официальный скрипт get.docker.com"
        curl -fsSL https://get.docker.com | $SUDO sh
        ;;
    esac
    command -v docker >/dev/null 2>&1 || die "docker так и не появился, поставь руками: https://docs.docker.com/engine/install/"
    ok "docker установлен: $(docker --version)"
  fi

  # служба + автозапуск
  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now docker >/dev/null 2>&1 \
      && ok "docker.service включен (автозапуск при загрузке)" \
      || warn "не смог включить docker.service, подними его сам"
  fi

  # чтобы docker работал без sudo (для алиаса ntlms и родного запуска)
  local u="${SUDO_USER:-${USER:-}}"
  if [ -n "$u" ] && ! id -nG "$u" 2>/dev/null | grep -qw docker; then
    $SUDO usermod -aG docker "$u" 2>/dev/null \
      && warn "добавил $u в группу docker — заработает после повторного входа; сейчас работаю через sudo"
  fi

  # compose plugin
  if $SUDO docker compose version >/dev/null 2>&1; then
    ok "docker compose plugin на месте: $($SUDO docker compose version --short 2>/dev/null || echo ok)"
  else
    warn "compose plugin не найден, пробую доставить"
    case "$PKG_FAM" in
      apt)  $SUDO apt-get install -y -qq docker-compose-plugin ;;
      dnf)  $SUDO dnf -y install docker-compose-plugin ;;
      apk)  $SUDO apk add --no-cache docker-cli-compose ;;
    esac
    $SUDO docker compose version >/dev/null 2>&1 || die "docker compose plugin недоступен"
    ok "docker compose plugin установлен"
  fi
}

# как вызывать docker в этой сессии (если группа не подхватилась — через sudo)
resolve_docker_cmd() {
  if docker info >/dev/null 2>&1; then
    DOCKER="docker"
  else
    DOCKER="$SUDO docker"
    warn "docker доступен только через sudo в этой сессии (логин в группу docker применится после перезахода)"
  fi
}
