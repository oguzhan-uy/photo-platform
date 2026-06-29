#!/usr/bin/env bash
# Nightly pg_dump → gzip → upload to Cloudflare R2.
#
# Runs as the 'deploy' user via cron (see cloud-init/bootstrap.yaml):
#   0 2 * * * /opt/photo/scripts/backup.sh >> /var/log/photo-backup.log 2>&1
#
# Keeps R2 within free tier (10 GB/month): at ~5 MB per compressed dump,
# 30 days of history uses ~150 MB. Add an R2 lifecycle rule to auto-delete
# objects under backups/ after 30 days.
#
# Prereqs on host:
#   - awscli installed (done by cloud-init)
#   - /opt/photo/.env sourced (R2_* and DATABASE_URL vars present)
#   - postgres container running under /opt/photo/docker-compose.yml

set -euo pipefail

# Load environment variables from the app .env file.
set -a
# shellcheck source=/dev/null
source /opt/photo/.env
set +a

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_FILE="/tmp/photo-db-${TIMESTAMP}.sql.gz"
R2_KEY="backups/pg_dump-${TIMESTAMP}.sql.gz"

echo "[$(date -u)] Starting backup → ${R2_KEY}"

# Dump from the running postgres container, stream directly to gzip.
docker compose -f /opt/photo/docker-compose.yml exec -T postgres \
  pg_dump -U photo -d photo | gzip > "${BACKUP_FILE}"

# Upload to R2 using the standard S3-compatible API.
# awscli reads credentials from the environment variables set above.
AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
aws s3 cp "${BACKUP_FILE}" \
  "s3://${R2_BUCKET}/${R2_KEY}" \
  --endpoint-url "${R2_ENDPOINT_URL}" \
  --region auto \
  --no-progress

rm -f "${BACKUP_FILE}"
echo "[$(date -u)] Backup complete → ${R2_KEY}"
