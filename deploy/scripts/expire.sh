#!/usr/bin/env bash
# Nightly gallery expiry — purge galleries whose expires_at has passed.
#
# Runs as the 'deploy' user via cron (see cloud-init/bootstrap.yaml):
#   15 3 * * * /opt/photo/scripts/expire.sh >> /var/log/photo-expire.log 2>&1
#
# Prereqs on host:
#   - /opt/photo/.env sourced (ADMIN_TOKEN present)
#   - API container running on localhost:8000

set -euo pipefail

set -a
# shellcheck source=/dev/null
source /opt/photo/.env
set +a

echo "[$(date -u)] Triggering gallery expiry"
curl -sf -X POST \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  http://localhost:8000/admin/expire-galleries
echo "[$(date -u)] Expiry complete"
