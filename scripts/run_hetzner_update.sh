#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

REPO="/home/marius/nivel-dunare"
LOCK_DIR="/home/marius/.local/state/nivel-dunare"
LOCK_FILE="${LOCK_DIR}/update.lock"
TMP_DIR=""

log() {
    printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

cleanup() {
    if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
}

abort_rebase() {
    git rebase --abort >/dev/null 2>&1 || true
}

sync_branch() {
    git fetch origin main

    local ahead behind
    read -r ahead behind < <(
        git rev-list --left-right --count HEAD...origin/main
    )

    if (( behind > 0 )); then
        if (( ahead > 0 )); then
            log "Remote și local au avansat; încerc rebase controlat."
            if ! git rebase origin/main; then
                abort_rebase
                log "Rebase eșuat; este necesară intervenție manuală."
                return 1
            fi
        else
            git merge --ff-only origin/main
        fi
    fi

    git fetch origin main
    read -r ahead behind < <(
        git rev-list --left-right --count HEAD...origin/main
    )

    if (( behind > 0 )); then
        log "Ramura locală este încă în urma origin/main."
        return 1
    fi

    if (( ahead > 0 )); then
        log "Public ${ahead} commit(uri) în GitHub."
        git push origin main
    fi
}

trap cleanup EXIT

mkdir -p "${LOCK_DIR}"
exec 9>"${LOCK_FILE}"

if ! flock -n 9; then
    log "Există deja o actualizare în curs; rularea este omisă."
    exit 0
fi

cd "${REPO}"

log "Pornire actualizare AFDJ."

if [[ -n "$(git status --porcelain)" ]]; then
    log "Repository-ul conține modificări locale. Actualizarea este oprită."
    git status --short
    exit 1
fi

sync_branch

TMP_DIR="$(mktemp -d)"

curl_common=(
    --fail
    --show-error
    --silent
    --location
    --compressed
    --retry 2
    --retry-delay 5
    --connect-timeout 15
    --max-time 90
    --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    --header "Accept-Language: ro-RO,ro;q=0.9,en;q=0.8"
    --referer "https://www.afdj.ro/ro/cotele-dunarii"
)

log "Descarc XML-ul AFDJ."
curl "${curl_common[@]}" \
    --header "Accept: application/xml,text/xml;q=0.9,*/*;q=0.1" \
    --output "${TMP_DIR}/afdj.xml" \
    "https://www.afdj.ro/ro/tabel_cotele_dunarii/xml"

log "Descarc pagina HTML AFDJ."
curl "${curl_common[@]}" \
    --header "Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1" \
    --output "${TMP_DIR}/afdj.html" \
    "https://www.afdj.ro/ro/cotele-dunarii"

log "Rulez ingestia."
python3 -m scripts.ingest_afdj \
    --xml-file "${TMP_DIR}/afdj.xml" \
    --html-file "${TMP_DIR}/afdj.html" \
    --source live-hetzner-systemd

log "Calculez scorurile prognozelor."
python3 -m scripts.calculate_forecast_scores

log "Construiesc datele publice."
python3 -m scripts.build_public_data

log "Validez repository-ul."
python3 -m scripts.validate_repository

log "Rulez testele."
python3 -m unittest discover -s tests -v

log "Rulez smoke testul portalului."
python3 -m scripts.smoke_test_site

git add -- data public/data

if git diff --cached --quiet; then
    log "Nu există date noi de publicat."
    exit 0
fi

observation_date="$(
    python3 -c \
    "import json; print(json.load(open('data/public/status.json', encoding='utf-8'))['latest_measurement_date'])"
)"

git commit -m "data: update AFDJ observations ${observation_date}"

sync_branch

log "Actualizarea AFDJ s-a încheiat cu succes."
