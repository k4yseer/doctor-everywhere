# Doctor Everywhere

Telehealth-style consultation platform built as a microservices system for an Enterprise Solution Development (ESD) project. The backend is a set of **atomic** and **composite** Flask services backed by MySQL, RabbitMQ, and Kong. The **frontend** is a Vue 3 + TypeScript + Vite single-page app.

## Repository layout

| Path | Description |
|------|-------------|
| `backend/` | Docker Compose stack, `kong.yml` API gateway, atomic services under `atomic/`, orchestration under `composite/` |
| `frontend/` | Vue 3 UI (PrimeVue, Tailwind, Pinia, Vue Router) |

Service-specific notes live in README files under `backend/atomic/*` and `backend/composite/*` where present.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- [Node.js](https://nodejs.org/) (current LTS recommended) and npm, for local frontend development

## Backend (Docker)

From the `backend` directory:

1. **Environment** — Copy the example env file and fill in secrets (patient DB, Resend, Stripe, Zoom, etc.):

   ```bash
   cd backend
   cp .env.example .env
   ```

2. **Start the stack** (builds images on first run):

   ```bash
   docker compose -f compose.yaml up --build
   ```

   This brings up MySQL instances per service, RabbitMQ, Kong in DB-less declarative mode, and all Flask services defined in `compose.yaml`.

3. **Seed the database** — Before seeding, open `seed_scripts/common_seed.json` and replace the placeholder email(s) with your own email address so you receive any notifications the app sends:

   ```json
   "email": "your@email.com"
   ```

   Then, with the stack running, seed all services:

   ```bash
   bash seed_scripts/seed_all.sh
   ```

### Useful endpoints (local defaults)

- **Swagger Documentation:** [http://localhost:8080](http://localhost:8080) — overview of all endpoints
- **Kong proxy (API gateway):** [http://localhost:8000](http://localhost:8000) — routes declared in `backend/kong.yml` (e.g. `/join-queue`, `/setup-consultation`, `/make-prescription`, and consultation history under `/consultation-history/...`).
- **Kong Admin API:** [http://localhost:8001](http://localhost:8001)
- **Kong Manager (read-only GUI):** [http://localhost:8002](http://localhost:8002)
- **RabbitMQ management UI:** [http://localhost:15672](http://localhost:15672) — default credentials `guest` / `guest`
- **Prometheus:** [http://localhost:9090](http://localhost:9090) — metrics scraping and querying
- **Grafana:** [http://localhost:3000](http://localhost:3000) — dashboards for service metrics; default credentials `admin` / `admin`

Individual services also expose host ports (5001–5015 range and dedicated MySQL ports); see `backend/compose.yaml` for the authoritative mapping.

## Frontend (local dev)

From the `frontend` directory:

```bash
cd frontend
npm install
npm run dev
```

The dev server URL is printed in the terminal (Vite default is often `http://localhost:5173`).

### Environment variables

Copy `frontend/.env.example` to `frontend/.env` if you need to override defaults. Notable variables:

- `VITE_API_GATEWAY_URL` — base URL used by the shared Axios client (`src/core/apiClient.ts`). Point this at the gateway or backend you are exercising (e.g. Kong on port `8000` for composite routes).
- `VITE_STRIPE_PUBLISHABLE_KEY` — stripe key

During development, `frontend/vite.config.ts` may proxy `/api` to a local service (e.g. appointment); adjust the proxy target if your ports differ from `compose.yaml`.

## Tech stack (summary)

- **Backend:** Python / Flask microservices, SQLAlchemy + MySQL, RabbitMQ (AMQP), Kong gateway
- **Frontend:** Vue 3, TypeScript, Vite, PrimeVue, Tailwind CSS, Pinia, Axios
