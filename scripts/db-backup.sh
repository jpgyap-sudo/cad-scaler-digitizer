#!/bin/sh
# =============================================================================
# CAD Scaler Digitizer — Automated Database Backup
# Run daily via cron. Backs up Postgres to Spaces or local file.
#
# Usage:
#   ./scripts/db-backup.sh                    # local backup only
#   ./scripts/db-backup.sh --upload           # local + Spaces upload
# =============================================================================
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
FILENAME="cad_digitizer_${TIMESTAMP}.sql.gz"
LOCAL_PATH="${BACKUP_DIR}/${FILENAME}"

mkdir -p "${BACKUP_DIR}"

echo "[db-backup] Backing up Postgres..."

docker compose exec -T postgres pg_dump \
  -U "${PG_USER:-postgres}" \
  -d "${PG_DATABASE:-cad_reference_library}" \
  --no-owner \
  --no-acl \
  --compress=9 \
  > "${LOCAL_PATH}"

echo "[db-backup] Local backup saved: ${LOCAL_PATH} ($(du -h "${LOCAL_PATH}" | cut -f1))"

# Upload to Spaces if --upload flag
if [ "$1" = "--upload" ]; then
  echo "[db-backup] Uploading to Spaces..."
  docker compose exec -T python-worker python -c "
import boto3, os
s3 = boto3.client('s3',
  endpoint_url='${SPACES_ENDPOINT:-https://sgp1.digitaloceanspaces.com}',
  region_name='${SPACES_REGION:-sgp1}',
  aws_access_key_id='${SPACES_KEY}',
  aws_secret_access_key='${SPACES_SECRET}',
  config=boto3.session.Config(signature_version='s3v4'))
with open('${LOCAL_PATH}', 'rb') as f:
  s3.upload_fileobj(f, '${SPACES_BUCKET}', 'backups/postgres/${FILENAME}',
    ExtraArgs={'ACL': 'private'})
print('Uploaded: s3://${SPACES_BUCKET}/backups/postgres/${FILENAME}')
"
fi

# Clean up old backups (keep last 7 days)
find "${BACKUP_DIR}" -name "cad_digitizer_*.sql.gz" -mtime +7 -delete

echo "[db-backup] Complete."
