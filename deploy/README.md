# Deployment Guide

This app uses GitHub Actions to run tests on every push/PR to `main` and auto-deploys to a single VPS when commits land on `main`. Deployment is a `git pull` + `docker compose up -d --build` over SSH.

## Prerequisites on the server

- Ubuntu 22.04 LTS (or similar Linux with systemd)
- Docker Engine + Docker Compose v2
- git
- A non-root user `deploy` with sudo-free docker access
- SSH key-based access for the `deploy` user (password auth disabled)

## One-time server setup

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/deepmory
sudo chown deploy:deploy /opt/deepmory
```

Install docker (Ubuntu):

```bash
curl -fsSL https://get.docker.com | sudo sh
```

### SSH key from GitHub Actions to server

On your local machine:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deepmory_deploy -N ""
ssh-copy-id -i ~/.ssh/deepmory_deploy.pub deploy@<SERVER_IP>
```

Add the private key contents (`cat ~/.ssh/deepmory_deploy`) to the repo's GitHub Secrets as `SSH_PRIVATE_KEY`. Also add:

- `SSH_HOST` — server IP or domain
- `SSH_USER` — `deploy`
- `SSH_PORT` — `22` (or custom)

### SSH key from server to GitHub (for private repos)

```bash
ssh-keygen -t ed25519 -C "deepmory-server" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
```

Paste the public key into your GitHub repo → Settings → Deploy keys (read-only is fine).

Configure SSH to use it for github.com:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
EOF
chmod 600 ~/.ssh/config
```

### Bootstrap

```bash
cd /opt/deepmory
REPO_URL=git@github.com:<org>/<repo>.git bash /path/to/bootstrap.sh
# Or after first clone, just run from inside the repo:
bash deploy/bootstrap.sh
```

### Configure secrets on the server

Edit `.env` files created from examples:

```bash
nano /opt/deepmory/.env
nano /opt/deepmory/server/.env
```

Populate real production values: DB passwords, SECRET_KEY, LLM API keys, Neo4j password, etc. These files are git-ignored; GitHub never sees them.

### First manual start

```bash
cd /opt/deepmory
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
docker compose ps
curl http://localhost:3000/api/v1/health
```

## Firewall

Open only: 22 (SSH), 80 (HTTP), 443 (HTTPS if using). Close 3000, 5432, 6379, 6333, 6334, 7474, 7687 — these are container-internal only in prod.

Example UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Hardening (recommended)

```bash
# /etc/ssh/sshd_config
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban
```

## Continuous deployment flow

Push/merge to `main`. GitHub Actions will:

1. Run backend pytest + frontend `npm run build` against ephemeral Postgres/Redis containers.
2. If tests pass, SSH to the VPS and run:
   - `git fetch origin main && git reset --hard origin/main`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml build`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
   - `docker image prune -f`
   - `curl /api/v1/health` to verify.

## Rotating secrets

Server-side: edit `/opt/deepmory/.env` or `/opt/deepmory/server/.env`, then:

```bash
cd /opt/deepmory
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Compose will recreate only containers whose env changed.

GitHub SSH key: regenerate a new key pair, update `SSH_PRIVATE_KEY` in GitHub Secrets, update `authorized_keys` on server, remove old key.

## Rollback

```bash
ssh deploy@<SERVER>
cd /opt/deepmory
git log --oneline -10
git reset --hard <commit-sha>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f backend
```

To return to the latest `main` afterwards: `git reset --hard origin/main && docker compose ... up -d --build`.

## Troubleshooting

- **Workflow fails at deploy step:** check SSH secrets. Verify manually: `ssh -i ~/.ssh/deepmory_deploy deploy@<SERVER>`.
- **Tests fail in CI only:** check the Postgres/Redis service container env in the workflow matches what your code expects.
- **Container unhealthy:** `docker compose logs <service>`. Health endpoint: `curl http://localhost:3000/api/v1/health`.
- **Disk fills up:** `docker image prune -af && docker volume prune` (careful: never delete `postgres_data`, `qdrant_data`, `neo4j_data`).
- **Port 80 already in use:** another nginx/apache running. `sudo systemctl stop nginx` if system nginx is running, or change the frontend port mapping in `docker-compose.prod.yml`.
