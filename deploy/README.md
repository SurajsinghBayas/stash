# Deploying Stash (AWS ap-south-1)

One EC2 instance runs nginx (frontend + `/api` proxy), the API and the worker. Postgres is RDS (`stash-db`), images
go to S3, content safety uses the moderator and vision models on Mantle. Everything is in **ap-south-1 (Mumbai)**.

```
browser ──https──> nginx ──/──────> /srv/stash/frontend/dist (static)
                         └─/api/──> uvicorn 127.0.0.1:4000 (stash-api) ──> RDS stash-db (private)
                                    python -m app.worker  (stash-worker) ──> S3, Bedrock, Mantle, Voyage, Resend
```

## 1. AWS resources (console, region Mumbai)

1. **S3 bucket** `stash-uploads-<something-unique>`: Block all public access ON. Then Permissions → CORS:
   ```json
   [{"AllowedOrigins": ["https://YOUR_DOMAIN"], "AllowedMethods": ["PUT", "GET"],
     "AllowedHeaders": ["*"], "MaxAgeSeconds": 3000}]
   ```
2. **IAM role for EC2** `stash-ec2`: IAM → Roles → Create → AWS service / EC2 → attach an inline policy:
   ```json
   {"Version": "2012-10-17", "Statement": [
     {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET/*"}]}
   ```
3. **EC2 instance**: EC2 → Launch instance
   - Name `stash-web`, AMI **Ubuntu Server 24.04 LTS (64-bit Arm)**, type **t4g.small** (2 GB)
   - Key pair: create `stash` (.pem), save it to `~/.ssh/stash.pem`, `chmod 400` it
   - Network: same VPC as `stash-db`; auto-assign public IP on. Security group `stash-web-sg`:
     SSH 22 from **My IP**, HTTP 80 and HTTPS 443 from anywhere
   - Storage 20 GB gp3. Advanced details → IAM instance profile: `stash-ec2`
4. **Elastic IP**: EC2 → Elastic IPs → Allocate → Associate with `stash-web` (the IP then survives restarts).
5. **Let the instance reach the database**: RDS security group `stash-db-sg` → inbound
   PostgreSQL 5432, source = security group `stash-web-sg`.
6. **DNS**: at your domain registrar add an `A` record `YOUR_DOMAIN → <elastic IP>`.

## 2. Set up the server (from your Mac, repo root)

```bash
export STASH_HOST=ubuntu@<elastic-ip> STASH_KEY=~/.ssh/stash.pem STASH_DOMAIN=<your domain>
./deploy/deploy.sh setup
```

## 3. Database and app login

After step 4 (the server's `backend/.env` holds `DATABASE_URL`), run on the server:
```bash
sudo bash /srv/stash/deploy/db-setup.sh      # asks for the RDS master password (master user: postgres)
```
It creates the database and the `stash_app` login if missing, sets the login's password to the one in `DATABASE_URL`,
enables pgvector and hands the schema to the app. Safe to run again; run it whenever the password in `.env` changes.

## 4. Production `.env` (on the server, never in git)

```bash
sudo -u stash nano /srv/stash/backend/.env && sudo chmod 600 /srv/stash/backend/.env
```
Start from your local `backend/.env` and change:

| Key | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_URL` | `https://YOUR_DOMAIN` |
| `DATABASE_URL` | `postgresql://stash_app:<pw>@stash-db.cv4i600y6bxd.ap-south-1.rds.amazonaws.com:5432/stash?sslmode=require` |
| `DATABASE_URL_DIRECT` | delete the line (or same as `DATABASE_URL`) |
| `JWT_SECRET` | new value: `python3 -c 'import secrets;print(secrets.token_urlsafe(48))'` |
| `SMTP_*`, `MAIL_FROM` | Resend values (uncommented), `MAIL_FROM=Stash <no-reply@YOUR_DOMAIN>` once the domain is verified in Resend |
| `S3_BUCKET` | your bucket |
| `SAFETY_REQUIRED` | `true` |
| `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | **delete the lines entirely** (empty values would override the instance role) |
| `LOCAL_UPLOAD_DIR` | delete |

The API refuses to start in production without `SMTP_HOST`, `S3_BUCKET` and the AI key (`OPENAI_API_KEY`, `OPENAI_BASE_URL`), which the safety moderator needs.

## 5. Deploy

```bash
./deploy/deploy.sh
```
Builds the frontend locally, ships code, runs `uv sync` and `alembic upgrade head`, restarts both services and
prints `/health/ready`. Run it again for every release.

## 6. HTTPS

```bash
ssh -i $STASH_KEY $STASH_HOST 'sudo certbot --nginx -d YOUR_DOMAIN --redirect -m you@example.com --agree-tos -n'
```
Certbot renews automatically.

## 7. OAuth and mail

- Google Cloud Console → Credentials → your OAuth client → add redirect URI
  `https://YOUR_DOMAIN/api/v1/auth/oauth/google/callback` and JavaScript origin `https://YOUR_DOMAIN`.
- X developer portal → User authentication settings → callback `https://YOUR_DOMAIN/api/v1/auth/oauth/x/callback`,
  website `https://YOUR_DOMAIN`.
- Resend → Domains → add YOUR_DOMAIN and the DNS records it shows. Until verified it only delivers to your own address.

## Operating

```bash
journalctl -u stash-api -f          # API logs
journalctl -u stash-worker -f       # worker logs
sudo systemctl restart stash-api stash-worker
```

## CI/CD (GitHub Actions)

`.github/workflows/ci-cd.yml` runs on every push and pull request: ruff + backend tests (Postgres 17 service) and
the frontend typecheck/build. On a push to `main`, once both pass, it SSHes into the server and runs
`deploy/remote-deploy.sh <sha>`: fetch that commit, `uv sync`, `alembic upgrade head`, `npm ci && npm run build`,
refresh systemd units if they changed, restart, and wait for `/health/ready`. A failed health check fails the run.

One-time setup:

1. **Deploy key** (on your Mac). It is used only by CI:
   ```bash
   ssh-keygen -t ed25519 -N "" -C stash-ci-deploy -f ~/.ssh/stash-ci-deploy
   ```
2. **Lock the key to the deploy script** (on the server). CI can then run nothing else, not even a shell:
   ```bash
   echo 'command="sudo /srv/stash/deploy/remote-deploy.sh \"$SSH_ORIGINAL_COMMAND\"",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty PASTE_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys
   ```
   (`PASTE_PUBLIC_KEY_HERE` = the whole line of `~/.ssh/stash-ci-deploy.pub`.)
3. **GitHub secrets** (on your Mac, repo root):
   ```bash
   gh secret set DEPLOY_SSH_KEY < ~/.ssh/stash-ci-deploy
   gh secret set DEPLOY_HOST --body 13.235.184.92
   ssh-keyscan -t ed25519 13.235.184.92 2>/dev/null | gh secret set DEPLOY_KNOWN_HOSTS
   ```
4. **Security group**: GitHub's runners use changing IPs, so SSH (22) must allow `0.0.0.0/0`. Password login is off
   on EC2 Ubuntu and the CI key can only run the deploy script.

Manual run: GitHub → Actions → CI/CD → Run workflow. Server-side by hand: `sudo /srv/stash/deploy/remote-deploy.sh $(git -C /srv/stash rev-parse origin/main)`.
