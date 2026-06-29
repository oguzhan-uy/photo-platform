# Photo Delivery Platform

Async photo delivery for event/sports photographers: per-client galleries, secure
delivery via presigned URLs, and face-similarity search so clients can find themselves
in a large shoot.

## What's in here

- **FastAPI** backend with per-gallery passcode auth and short-lived signed tokens
- **RQ worker** for async ingest, thumbnailing, face embedding, and HDBSCAN clustering
- **Postgres + pgvector** — relational data and face embeddings in the same DB
- **Cloudflare R2** for object storage (presigned PUT upload, presigned GET delivery)
- **InsightFace** (ArcFace) embeddings → pgvector HNSW search → face cluster UI
- **Prometheus + Grafana** dashboards provisioned as code
- **React + TypeScript** gallery UI with face-cluster filtering and lightbox
- **Terraform + cloud-init** for reproducible VPS provisioning
- **Cloudflare Tunnel** — zero inbound ports on the host
- **GitHub Actions → GHCR → Watchtower** pull-based CI/CD

## Auth

- **Admin (photographer):** static bearer token (`ADMIN_TOKEN`) on all `/admin/*` routes.
  Use `/docs` to manage clients, galleries, and uploads.
- **Client:** POST a passcode to `/access/{gallery_id}`, get a short-lived signed token
  scoped to that gallery. Cross-gallery access is structurally impossible — every
  `/me/*` route derives the gallery from the token, never from a user-supplied ID.

## Running locally

```bash
cp .env.example .env
docker compose up --build
```

API at `http://localhost:8000`, docs at `http://localhost:8000/docs`.
Prometheus at `http://localhost:9090`, Grafana at `http://localhost:3000` (admin/admin).
MinIO console at `http://localhost:9001` (minioadmin/minioadmin).

### Frontend dev server

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. Vite proxies API calls to `:8000`.

### Share a gallery link

```
http://localhost:5173/?g=<gallery_id>
```

### Quick smoke test

```bash
A="Authorization: Bearer dev-admin-token-change-me"

CID=$(curl -s -H "$A" -H 'content-type: application/json' \
      localhost:8000/admin/clients -d '{"display_name":"Alice"}' \
      | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')

GID=$(curl -s -H "$A" -H 'content-type: application/json' \
      localhost:8000/admin/galleries \
      -d "{\"client_id\":\"$CID\",\"title\":\"Wedding\",\"passcode\":\"shoot2026\"}" \
      | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')

echo "Gallery: http://localhost:5173/?g=$GID  passcode: shoot2026"
```

## Tests

Runs on SQLite — no Docker needed:

```bash
pip install -r requirements.txt
pytest -q
```

Covers: access-control isolation, idempotent ingest, job failure/dead-letter,
face pipeline consent gating, search scoping, GDPR erasure and DeletionLog.

## Deploying

The stack is a single `docker-compose.yml`. You need:

1. A Linux VPS with Docker installed (tested on Ubuntu 24.04 ARM64)
2. Cloudflare account with your domain
3. Cloudflare R2 bucket + credentials
4. A GitHub repo so Actions can build the arm64 image to GHCR

### Provision the server

Any VPS works. Hetzner CAX11 (ARM64, 4 GB RAM) is a good cheap option.

Create the server with Ubuntu 24.04, SSH in, and install Docker:

```bash
curl -fsSL https://get.docker.com | sh
```

### Configure

```bash
git clone https://github.com/<you>/photo-platform /opt/photo
cd /opt/photo
cp .env.example .env
nano .env   # fill in all values
```

### Cloudflare Tunnel

1. Cloudflare Zero Trust → Networks → Tunnels → Create tunnel
2. Add two public hostnames:
   - `gallery.<domain>` → `http://api:8000`
   - `grafana.<domain>` → `http://grafana:3000`
3. Copy the tunnel token → `CLOUDFLARE_TUNNEL_TOKEN` in `.env`
4. Protect `grafana.<domain>` with a Cloudflare Access policy (email OTP is free)

### Start

```bash
docker login ghcr.io -u <github-user> --password-stdin <<< <ghcr-token>
docker compose --profile prod up -d
```

Watchtower polls GHCR every 5 minutes. Push to `main` and the server updates itself.

### Backups

A nightly `pg_dump` can be wired up via cron:

```bash
# crontab -e
0 2 * * * /opt/photo/deploy/scripts/backup.sh >> /var/log/photo-backup.log 2>&1
```

## Layout

```
app/
  models/       Client, Gallery, Photo, Face, JobAudit, DeletionLog
  routers/      admin.py · client.py
  schemas.py    Pydantic I/O
  storage.py    R2 wrapper (boto3)
  face_search.py  pgvector cosine search
  metrics.py    Prometheus counters/histograms
worker/
  jobs/         ingest · embed · cluster · expire
migrations/     Alembic versions
frontend/
  src/
    api/        client.ts · gallery.ts
    lib/        faceCrop.ts
    hooks/      useAuth.ts
    components/ LoginScreen · GalleryView · PeopleRow · PhotoGrid · Lightbox
infra/
  terraform/    VCN + subnet + instance + reserved IP (OCI)
  cloud-init/   bootstrap.yaml
deploy/
  prometheus/   config + alert rules
  grafana/      provisioned dashboards
  scripts/      backup.sh · keepalive.sh
.github/
  workflows/    build.yml (buildx arm64 → GHCR)
tests/
```

## Design notes

**Modular monolith + one queue.** The workload is a solo photographer — tens of thousands
of photos, not billions. FastAPI + RQ on Redis is the right fit; microservices would add
operational overhead with no benefit at this scale.

**Sync SQLAlchemy in an async framework.** API-side DB calls are fast metadata reads.
Blocking the event loop for sub-millisecond queries is fine; async SQLAlchemy adds
complexity for no measurable gain here.

**Direct-to-R2 presigned PUT.** The API issues a presigned URL and steps aside. Photo
bytes go straight from the photographer's machine to R2 — no memory pressure, no proxy
bottleneck, free egress.

**Presigned GET delivery (5-minute TTL).** No bucket is ever public. Short enough to be
useless if leaked; long enough for a browser to load a gallery. The frontend re-fetches
before expiry (4-minute staleTime).

**Content-hash idempotent ingest.** Re-uploading the same file is a no-op. Re-running the
ingest job on an already-processed photo is also a no-op. Bulk uploads are safe to retry.

**pgvector for face embeddings.** Keeps everything in one Postgres instance — no separate
vector DB. HNSW index gives good recall/latency on modest data volumes.

**Verifiable deletion (DeletionLog).** Every GDPR erasure, gallery expiry, and biometric
revocation writes an immutable row with exact counts. The photographer can produce it as
compliance evidence.

**Zero inbound ports.** Cloudflare Tunnel makes an outbound QUIC connection to Cloudflare's
edge. The host has no open ingress rules; all traffic is proxied by Cloudflare.

**Pull-based CI/CD via Watchtower.** No SSH keys in GitHub Actions, no inbound access
required. The host pulls new images from GHCR on a timer.
