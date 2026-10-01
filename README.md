<div align="center">

# 💧 Water Filter Monitor

**Simulated IoT system for real-time water filter health monitoring and clogging-time prediction.**

Virtual sensor, MQTT messaging, time-series storage, ML-based prediction, live dashboard, dual-channel alerting —
running locally with Docker Compose and on AWS (ECS Fargate) provisioned with Terraform.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?logo=eclipsemosquitto&logoColor=white)
![InfluxDB](https://img.shields.io/badge/InfluxDB-2.7-22ADF6?logo=influxdb&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-13-F46800?logo=grafana&logoColor=white)
![scikit--learn](https://img.shields.io/badge/scikit--learn-ML%20prediction-F7931E?logo=scikitlearn&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-AWS-7B42BC?logo=terraform&logoColor=white)
![CI](https://github.com/danielailenei/water-filter-monitor/actions/workflows/ci.yml/badge.svg)
![Deploy](https://github.com/danielailenei/water-filter-monitor/actions/workflows/deploy.yml/badge.svg)

</div>

---

## 📖 Contents

- [What it does](#-what-it-does)
- [Architecture](#-architecture)
- [Tech stack](#-tech-stack)
- [Quick start (local)](#-quick-start-local)
- [Deployment on AWS](#-deployment-on-aws)
- [CI/CD](#-cicd)
- [Monitoring and cost](#-monitoring-and-cost)
- [Backend API](#-backend-api)
- [How the prediction works](#-how-the-prediction-works)
- [Alerting](#-alerting)
- [Configuration](#-configuration)
- [Security](#-security)
- [Project structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [Development notes](#-development-notes)

---

## 🎯 What it does

Simulates an IoT sensor mounted on a water filter, measuring **differential
pressure**, **flow rate**, and **turbidity** in real time. As the filter
clogs, pressure rises exponentially and flow drops — just like a real
filter. The system:

- 📡 collects data over **MQTT**, the standard IoT messaging protocol;
- 🗄️ stores the full history in a **time-series database** (InfluxDB);
- 📊 displays it live on a **built-in dashboard** (served by the backend at
  `/`, in Romanian, times in Europe/Bucharest) and on an auto-provisioned
  **Grafana dashboard** for deeper analysis;
- 🤖 **predicts**, via a regression model, how long remains before the
  filter fully clogs, next to the simulator's exact value for comparison;
- 🔔 sends **email + push notifications** (ntfy.sh) at 80%, 90%, and 100% of
  clogging capacity, with automatic retry on transient network failures;
- ☁️ runs the same containers on **AWS ECS Fargate**, built and deployed by
  **GitHub Actions**, with the whole infrastructure in **Terraform**.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    S["🌡️ Virtual sensor<br/>Python"]
    M["📡 Mosquitto<br/>MQTT broker · :1883"]
    W["🔁 Worker<br/>ingest + alerting"]
    B["⚙️ FastAPI backend<br/>API + dashboard · :8000"]
    I[("🗄️ InfluxDB<br/>:8086")]
    G["📊 Grafana<br/>:3000"]
    C["💻 Browser<br/>dashboard / REST"]
    A["🔔 Alerts<br/>email + push (ntfy.sh)"]

    S -- "publish JSON" --> M
    M -- "subscribe" --> W
    W -- "writes points" --> I
    W -- "threshold crossed" --> A
    I -- "queries" --> B
    I -- "queries (Flux)" --> G
    B -- "/ /latest /history /predict" --> C

    style S fill:#2b2b2b,stroke:#7dd3fc,color:#fff
    style M fill:#2b2b2b,stroke:#c084fc,color:#fff
    style W fill:#2b2b2b,stroke:#a3e635,color:#fff
    style B fill:#2b2b2b,stroke:#34d399,color:#fff
    style I fill:#2b2b2b,stroke:#38bdf8,color:#fff
    style G fill:#2b2b2b,stroke:#fb923c,color:#fff
    style C fill:#2b2b2b,stroke:#f472b6,color:#fff
    style A fill:#2b2b2b,stroke:#facc15,color:#fff
```

Every component runs as a container. The **worker** (one instance) is the
only MQTT subscriber: it stores each reading and sends the alerts. The
**backend** only reads from InfluxDB, so it is stateless and can run as several
replicas; both use the same image with a different command. The same images
run locally (Docker Compose) and on AWS (ECS Fargate); only the addresses
differ — compose service names locally, `*.wfm.local` (AWS Cloud Map) and
CloudFront on AWS.

---

## 🧩 Tech stack

| Component | Technology | Role |
|---|---|---|
| Virtual sensor | Python 3.11+, `paho-mqtt` | Simulates filter degradation, publishes to MQTT |
| Message broker | Eclipse Mosquitto 2 | MQTT transport, sensor → worker |
| Worker | Python, `paho-mqtt`, `influxdb-client` | Single instance: stores readings, sends alerts, keeps alert state in InfluxDB |
| Backend | FastAPI, `influxdb-client`, `scikit-learn` | Stateless REST API, ML prediction, built-in dashboard |
| Database | InfluxDB 2.7 | Time-series storage of readings |
| Visualization | Grafana 13 | Live dashboard, auto-provisioned |
| Alerting | `smtplib` (SMTP) + ntfy.sh | Email + phone push at 80/90/100% clogging |
| Local orchestration | Docker Compose | Start/stop the whole stack with one command |
| Cloud | AWS ECS Fargate (ARM64), ALB, CloudFront, EFS, Cloud Map, SSM | Production-like deployment |
| Infrastructure as code | Terraform (S3 remote state) | Layered, create/destroy on demand |
| CI/CD | GitHub Actions + OIDC | Build, scan, deploy; on-demand stage environment |

---

## 🚀 Quick start (local)

**Prerequisites:** Docker Desktop (with the WSL2 engine on Windows).

```bash
# 1. Copy the env template (defaults are fine for local dev; never commit .env)
cp .env.example .env

# 2. Start the whole stack: Mosquitto, InfluxDB, worker, backend, virtual sensor, Grafana
docker compose up -d --build

# 3. Verify
curl.exe http://localhost:8000/latest
curl.exe http://localhost:8000/predict
```

| Service | URL | Auth |
|---|---|---|
| 💧 Dashboard | http://localhost:8000 | — |
| 📊 Grafana | http://localhost:3000 | `admin` / value from `.env` |
| 🗄️ InfluxDB UI | http://localhost:8086 | `admin` / value from `.env` |
| ⚙️ Backend API | http://localhost:8000/docs | — |

In Grafana the *"Water Filter Monitor"* dashboard is already provisioned, with
charts refreshing every 5 seconds.

To iterate on the sensor without rebuilding its image, stop the container and
run it with plain Python — it reads the same `config.yaml`:

```bash
docker compose stop sensor
cd sensor
pip install -r requirements.txt
python virtual_sensor.py
```

> 🔔 To enable email/push alerts, copy `.env.secrets.example` to
> `.env.secrets` and fill in your SMTP credentials and ntfy.sh topic (see
> comments in the file).

---

## ☁️ Deployment on AWS

The infrastructure lives in `terraform/`, split into layers with separate
state files in S3. The permanent layers cost almost nothing; the expensive
one (`stage-app`) is created and destroyed on demand.

```mermaid
flowchart LR
    U["👤 Browser"] -- "HTTPS" --> CF["CloudFront<br/>*.cloudfront.net"]
    CF -- "HTTP + secret header" --> ALB["ALB<br/>public subnets"]
    subgraph VPC["VPC stage 10.0.0.0/16 — private subnets, 2 AZ"]
        B["backend<br/>1–3 tasks, autoscaled"]
        G["grafana"]
        M["mosquitto"]
        W["worker<br/>1 task"]
        I["influxdb"]
        S["sensor"]
    end
    ALB -- "/" --> B
    ALB -- "/grafana/*" --> G
    S --> M --> W --> I
    B --> I
    G --> I
    I --- EFS[("EFS<br/>InfluxDB data")]
    W -- "NAT" --> N["SMTP · ntfy.sh"]
```

Detailed diagram with the official AWS icons — both VPCs with their two availability
zones and subnet CIDRs, the Docker containers (ECS tasks) in each AZ, peering, how the
tasks reach ECR, SSM, Cloud Map, CloudWatch and EFS, and the CI/CD path
([`diagrams/aws-architecture.drawio`](diagrams/aws-architecture.drawio), editable in
[draw.io](https://app.diagrams.net)):

![AWS architecture](diagrams/aws-architecture.png)

| Layer | What it creates | Lifetime |
|---|---|---|
| `bootstrap/` | S3 bucket for Terraform state (versioned, encrypted); its own state is stored in that bucket too | permanent |
| `shared/` | VPC `10.3.0.0/16`, ECR repositories, JumpHost (SSM only, stopped by default), GitHub OIDC provider + CI/CD roles, monthly budget, cost anomaly alert, cost allocation tags | permanent |
| `stage-base/` | VPC `10.0.0.0/16` + peering, security groups, EFS, ECS cluster, log groups, CloudWatch dashboard, secrets and the deployed image tag in SSM Parameter Store | permanent |
| `stage-app/` | NAT gateway, IAM task roles, Cloud Map (`wfm.local`), task definitions, 6 ECS services, ALB, CloudFront, backend autoscaling | **on demand** (~0.15 $/h) |
| `modules/network/` | reusable VPC module (public/private subnets in 2 AZ) | — |

Highlights:

- **ARM64 (Graviton) Fargate** tasks in private subnets; outbound traffic through NAT.
- **Secrets** in SSM Parameter Store (`SecureString`), injected by ECS; generated
  ones never touch the Terraform state (ephemeral + write-only).
- **HTTPS** via CloudFront's default certificate. The ALB accepts only the
  CloudFront prefix list **and** a secret origin header (403 otherwise).
- **InfluxDB data on EFS**, so it survives `stage-app` destroy/create.
- **Single-instance services** (InfluxDB, sensor, worker) deploy
  stop-then-start, so two copies never run at once (shared files, a second
  simulated filter, duplicate alerts).
- **Autoscaling**: the stateless backend scales 1–3 tasks on 50% average CPU.

**Day to day** everything runs from GitHub Actions (next section): a push to
`main` builds and deploys, and *Actions → Stage environment → Run workflow*
creates or destroys `stage-app` (create ~8 min, destroy ~10 min because of
CloudFront). The app address is printed in the run summary.

**From scratch** (AWS CLI profile `wfm`, Terraform ≥ 1.10), layer by layer —
each one reads the previous layers' outputs from their state in S3:

```powershell
$env:AWS_PROFILE = "wfm"
cd terraform\bootstrap   # chicken-and-egg: comment out the backend block in versions.tf,
terraform init; terraform apply   # create the bucket with local state, restore the block,
terraform init -migrate-state      # then move this layer's state into the bucket
cd ..\shared                                               # set cost_alert_email first:
Copy-Item terraform.tfvars.example terraform.tfvars        #   git-ignored, edit the address
terraform init; terraform apply                            # VPC, ECR, JumpHost, OIDC roles, budget
cd ..\stage-base;        terraform init; terraform apply   # VPC + peering, SGs, EFS, ECS cluster, SSM params
cd ..\..
powershell -ExecutionPolicy Bypass -File .\scripts\set-stage-secrets.ps1   # .env.secrets -> SSM (SMTP, ntfy)
powershell -ExecutionPolicy Bypass -File .\scripts\build-push.ps1         # ARM64 images -> ECR, tag = commit SHA -> SSM
cd terraform\stage-app;  terraform init; terraform apply   # ~8 min, prints app_url
terraform destroy                                          # when done
```

`stage-app` reads the image tag from SSM (`/wfm/stage/image_tag`); pass
`-var image_tag=<sha>` to run another version.

**Cost:** the permanent layers cost cents per month (stopped JumpHost disk,
EFS with a few MB, SSM parameters). `stage-app` costs ~0.15 $/h while it
runs, mostly the NAT gateway, the ALB and Fargate — hence create/destroy on
demand and the nightly destroy.

Helper scripts: `scripts/build-push.ps1` (build + push to ECR),
`scripts/set-stage-secrets.ps1` (upload `.env.secrets` to SSM),
`scripts/load-test.py` (HTTP load generator), `scripts/cpu-stress.py` (CPU
scaling test, see below), `scripts/dashboard-snapshot.py` (dashboard charts as PNG).

---

## 🔄 CI/CD

GitHub Actions authenticates to AWS with **OIDC** — no access keys stored in
GitHub. Each job gets a signed token; AWS STS exchanges it for 1-hour
credentials only if the token matches the role's trust policy exactly.

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | pull request to `main` | `terraform fmt` + `validate` (4 layers), Python byte-compile + `pip check`, ARM64 Docker build of the 4 images — no AWS access |
| `deploy.yml` | push to `main` touching app code | build ARM64 images on a native ARM runner → ECR (tag = short SHA) → fail on CRITICAL CVEs from the ECR scan → publish the tag to SSM → if `stage-app` is running: `terraform apply`, wait for ECS services, smoke test |
| `stage.yml` | manual (`create` / `destroy`), nightly at 20:00 UTC | on-demand environment: create `stage-app` + smoke test, or destroy it; the nightly run destroys a forgotten stack |

| IAM role | Who can assume it | Can do |
|---|---|---|
| `wfm-github-build` | jobs on `main` of this repo | push to the 4 `wfm/*` ECR repositories |
| `wfm-github-deploy` | jobs in the GitHub environment `stage` (restricted to `main`) | Terraform on `stage-app` only: its state object, NAT/ALB/ECS/Cloud Map/CloudFront, and `wfm-stage-*` IAM roles |

The deploy role can create IAM roles only with the **permissions boundary**
`wfm-stage-role-boundary` (ECR pull, ECS logs, `/wfm/stage/*` parameters, ECS
Exec), and cannot remove it — so a pipeline change cannot mint an admin role.
Both terraform workflows share a concurrency group, so only one run touches the
`stage-app` state at a time (S3 native locking guards local runs too).

---

## 📈 Monitoring and cost

**CloudWatch dashboard `wfm-stage`** (in `stage-base`, so it outlives each
`stage-app` run): backend CPU against the 50% scaling target, healthy backend
tasks behind the ALB, requests per minute, p50/p95 response time, 5xx errors,
and CPU/memory per service. The ALB gets a new ID on every create, so its
charts use `SEARCH` by name and merge successive stacks into one line; ECS
metrics are referenced directly by cluster and service name. No Container
Insights: the backend task count comes from the target group's
`HealthyHostCount`. `scripts/dashboard-snapshot.py <start> <end> <dir>` saves
every chart as a PNG.

**Scaling tests** (`stage-app` running, results in the dashboard):

| Test | Load | Result |
|---|---|---|
| `load-test.py` | HTTP on `/predict` (backend → InfluxDB) | backend 1 → 3 → 1 tasks; throughput limited by InfluxDB at 100% CPU — the bottleneck moves to the stateful tier |
| `cpu-stress.py` | CPU only, inside every backend task via ECS Exec (`nice 10`, new tasks included), plus a `/health` probe | 1 → 2 (~5 min) → 3, back to 1 about 18 min after the load stops; InfluxDB ~3% CPU; 0 failed probes, 0 ALB 5xx |

**Cost controls** (`terraform/shared/cost.tf`):

- monthly budget (20 $) that counts **usage only** — on the AWS Free Plan,
  credits would otherwise net the cost to ~0 and the alerts would never fire;
  email at 50/80/100% actual and 100% forecasted;
- Cost Anomaly Detection subscription: daily email for anomalies ≥ 2 $;
- cost allocation tags `Project` and `Layer` (set on every resource through
  provider `default_tags`, propagated to ECS tasks), so Cost Explorer can split
  the bill per layer;
- the expensive layer exists only on demand, with a nightly destroy.

The alert address comes from `cost_alert_email` in the git-ignored
`terraform/shared/terraform.tfvars`. AWS asks to verify that address (an
"Email verification" message from AWS User Notifications) before it delivers
budget alerts.

---

## 📡 Backend API

Locally at `http://localhost:8000` (interactive docs at `/docs`); on AWS at the CloudFront address.

| Endpoint | Description |
|---|---|
| `GET /` | Built-in dashboard (static HTML/CSS/JS, polls the endpoints below) |
| `GET /health` | Quick liveness check (also used by the ALB) |
| `GET /latest` | Most recent reading (last point in InfluxDB) |
| `GET /history?hours=24` | Reading history from InfluxDB (`hours` 0.05–720, fractional allowed) |
| `GET /predict?hours=24` | Prediction: time remaining until clogging, plus `R²` |
| `GET /alerts?hours=24` | Recent alert events written by the worker (threshold sent / filter reset) |
| `GET /config` | Public links for the dashboard (Grafana URL for the current environment) |

The dashboard is plain static files in `backend/static/`, mounted with FastAPI's
`StaticFiles`. It shares the backend's origin, so there is no CORS to configure.

---

## 🤖 How the prediction works

As a filter clogs, its hydraulic resistance grows **exponentially**. The filter
sits in series with the rest of the plumbing, fed at the mains supply pressure
`P_s` (4 bar), so with `x = R_filter / R_system`:

```
x(t) = x0 · e^(k·t)          pressure = P_s · x / (1 + x)          flow ∝ P_s − pressure
```

The pressure drop starts at the new-filter value, rises almost exponentially and
levels off smoothly at `P_s` (a fully blocked filter takes the whole supply
pressure) while the flow falls to zero. Inverting gives a transform that is
**linear in time**:

```
ln( pressure / (P_s − pressure) ) = ln(x0) + k·t
```

`ml_model.py` fits a linear regression (`scikit-learn`) on that transform vs
elapsed seconds, using only the **current filter cycle** (a pressure drop of
more than 0.3 bar or a gap of more than 10 min starts a new one), and solves for the time the
pressure reaches the clog threshold (`1.5 bar`). The `/predict` response also
returns `R²` so the caller can judge the fit; once past the threshold it reports
`clogged` and since when. Because `k` is learned from the data rather than read
from the simulator, the same model would work on real sensor readings. The
simulator's exact time-to-clog is published alongside, for comparison.

---

## 🔔 Alerting

`alerting.py` runs in the worker's MQTT message handler. On every reading it
computes the clogging percentage (`pressure ÷ threshold`) and fires a
notification when it crosses **80%, 90%, 100%**:

- each threshold fires **once per filter cycle**; the thresholds already
  notified are also saved in InfluxDB (`alert_event`) and restored when the
  worker starts, so a restart or redeploy does not repeat them;
- the worker runs as a **single instance** — alerting lives outside the
  scalable API, otherwise every API replica would send its own copy;
- if pressure drops below 50% (filter replaced / sensor restarted) the set
  resets, so the next cycle can alert again;
- each send (email over SMTP + push via [ntfy.sh](https://ntfy.sh)) is
  retried up to 3 times, so a transient network error doesn't drop an alert;
- alerts link to the dashboard and to Grafana (`APP_URL`, `GRAFANA_URL`);
  tapping the push notification opens the dashboard.

The messages (`alert_templates.py`, in Romanian) are an **HTML email** coloured
per level (amber / orange / red) with a plain-text fallback, and an ntfy push
published as JSON with Markdown, rising priority (3 → 5), an icon and action
buttons. Times are shown in `ALERT_TIMEZONE` (default `Europe/Bucharest`).

Credentials come from `.env.secrets` locally (git-ignored) and from SSM
Parameter Store on AWS. Without them, alerts are skipped and the rest of the
system runs normally.

---

## ⚙️ Configuration

| Where | Purpose |
|---|---|
| `sensor/config.yaml` | Simulation parameters — clogging rate, base values, `clog_threshold_bar`, `supply_pressure_bar` (mains pressure), raw-water turbidity, `time_acceleration`, publish interval |
| `.env` (from `.env.example`) | Local passwords/token read by `docker-compose.yml`; connection values for running the Python code outside Docker |
| `.env.secrets` (from `.env.secrets.example`) | SMTP + ntfy.sh credentials for alerting — **never committed** |
| `docker-compose.yml` | Local services, ports, volumes, `APP_URL` / `GRAFANA_URL` |
| `grafana/provisioning/` | Datasource + dashboard, baked into the Grafana image |
| `terraform/stage-app/task-definitions.tf` | Same settings for AWS (addresses, sizes, secrets from SSM) |

Environment variables read by the Python services (defaults in brackets):

| Variable | Used by | Purpose |
|---|---|---|
| `MQTT_BROKER` / `MQTT_PORT` / `MQTT_TOPIC` | sensor, worker | broker address [`localhost` / `1883` / `home/water/filter`] |
| `INFLUX_URL` / `INFLUX_TOKEN` / `INFLUX_ORG` / `INFLUX_BUCKET` | worker, backend | InfluxDB connection [`http://localhost:8086` / — / `disertatie` / `water_filter`] |
| `CLOG_THRESHOLD_BAR` | worker, backend | pressure that counts as clogged; base of the 80/90/100% alerts [`1.5`] |
| `SUPPLY_PRESSURE_BAR` | backend | mains pressure used by the prediction [`4.0`] — keep in sync with `sensor/config.yaml` |
| `APP_URL` / `GRAFANA_URL` | worker, backend | public links in alerts and on the dashboard [`http://localhost:8000` / `http://localhost:3000`] |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `ALERT_EMAIL_TO` | worker | email alerts [`smtp.gmail.com` / `465` / — ] |
| `NTFY_TOPIC` | worker | ntfy.sh topic for push alerts |
| `ALERT_TIMEZONE` | worker | time zone of the times in alerts [`Europe/Bucharest`] |

> Mosquitto allows anonymous access (`allow_anonymous true`) — fine for local
> development; on AWS it is reachable only from the sensor and worker
> security groups. For a real device fleet, add authentication and TLS.

---

## 🔒 Security

| Area | Measure |
|---|---|
| Access to AWS from CI | OIDC, no stored keys; two roles bound to this repo's immutable ID, `main` and the `stage` environment |
| IAM | least-privilege roles; roles created by the pipeline carry a permissions boundary |
| Secrets | SSM `SecureString`, injected by ECS at start; generated ones never in the Terraform state; `.env*` git-ignored |
| Network | tasks in private subnets; security group per service; ALB reachable only from CloudFront + secret header; JumpHost without inbound rules (SSM Session Manager) |
| Images | ARM64, OS packages upgraded at build, non-root user (uid 10001), ECR scan on push — deploy stops on CRITICAL findings; immutable tags |
| HTTP | HTTPS only (redirect), CloudFront security headers (HSTS, `nosniff`, `X-Frame-Options`, `Referrer-Policy`), no `Server` header |
| Supply chain | GitHub Actions pinned by commit SHA; Terraform provider versions locked (`.terraform.lock.hcl`) |
| State | S3 bucket versioned, encrypted, public access blocked, native locking |

---

## 📁 Project structure

```
water-filter-monitor/
├── docker-compose.yml          # local stack (same images as AWS)
├── .env.example                # local config template        ->  copy to .env
├── .env.secrets.example        # alerting credentials template ->  copy to .env.secrets
├── sensor/                     # virtual sensor (Python, MQTT publisher)
│   ├── virtual_sensor.py       #   main loop: compute reading, publish to MQTT
│   ├── filter_model.py         #   mathematical degradation model
│   └── config.yaml             #   simulation parameters
├── backend/                    # one image, two entry points
│   ├── main.py                 #   API: REST endpoints + ML prediction, serves static/
│   ├── worker.py               #   worker: MQTT -> InfluxDB + alerts (single instance)
│   ├── mqtt_subscriber.py      #   receives readings, writes them, checks alerts
│   ├── db_writer.py            #   InfluxDB wrapper (readings + alert state)
│   ├── ml_model.py             #   clogging-time prediction
│   ├── alerting.py             #   thresholds, persistence, sending with retry
│   ├── alert_templates.py      #   email (HTML + text) and ntfy message layout
│   └── static/                 #   built-in dashboard (index.html, style.css, app.js)
├── mosquitto/                  # broker config, baked into a custom image
├── grafana/                    # pinned Grafana + provisioning, baked into a custom image
├── .github/workflows/          # ci.yml, deploy.yml, stage.yml (see "CI/CD")
├── diagrams/                   # AWS architecture diagram (draw.io source + PNG)
├── scripts/                    # build/push, secrets upload, load + CPU scaling tests, dashboard snapshots
└── terraform/                  # AWS infrastructure (see "Deployment on AWS")
    ├── bootstrap/  shared/  stage-base/  stage-app/
    └── modules/network/
```

---

## 🩺 Troubleshooting

**`curl` in PowerShell shows a security warning** — it's an alias for
`Invoke-WebRequest`. Use `curl.exe` explicitly.

**`python` / `pip` not found on Windows** — the Microsoft Store stub is
intercepting. Install real Python (`winget install Python.Python.3.12`) and
reopen the terminal.

**Grafana shows "No data" on every panel** — usually the sensor isn't
running (`curl.exe http://localhost:8000/latest` returns `no_data`) or the
selected time range doesn't cover the data (widen it, top right).

**`docker compose up` fails with a WSL2 / virtualization error** — enable the
missing Windows components: run `wsl --install --no-distribution` as
Administrator, then restart.

**ECS task keeps restarting on AWS** — check its log group
(`/ecs/wfm-stage/<service>` in CloudWatch). A sensor task that starts before
Mosquitto is registered in Cloud Map fails once and is restarted by ECS; that
is expected (the worker can log one `Failed to resolve 'influxdb.wfm.local'`
for the same reason).

**GitHub Actions: `Not authorized to perform sts:AssumeRoleWithWebIdentity`** —
the token's `sub` claim does not match the role's trust policy. Check the
format this repository uses with
`gh api repos/<owner>/<repo>/actions/oidc/customization/sub` (immutable IDs:
`repo:owner@<id>/repo@<id>:...`) and set `github_repository` in
`terraform/shared` accordingly; environment jobs have `:environment:stage`,
not `:ref:...`.

**The app URL stopped working overnight** — the nightly `stage.yml` run
destroys `stage-app`; run *Stage environment → create* again. The CloudFront
address changes on every create.

**Git Bash turns `/wfm/stage/...` into a Windows path** (`ParameterNotFound`) —
prefix the command with `MSYS_NO_PATHCONV=1`, or use PowerShell.

**`Error acquiring the state lock` (412 PreconditionFailed)** — an interrupted
Terraform run left its `.tflock` object in S3 (for example, piping `terraform
plan` into `Select-Object -First N` stops the process early). Check *Lock Info*
(who, operation, when); if it is your own stale lock, run `terraform
force-unlock <ID>`. Write Terraform output to a file before filtering it.

**ECS Exec: `execute command agent isn't running`** — the agent starts some
seconds after the task is `RUNNING`; retry. `cpu-stress.py` retries on its own.
From PowerShell 5.1, pass commands with inner quotes through Python
`subprocess` — PowerShell strips them when calling native programs.

---

## 🛠️ Development notes

Built with an AI coding assistant (Claude Code): code was generated from my
requirements and design decisions, then applied, reviewed and verified in AWS
by me.
