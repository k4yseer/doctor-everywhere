# Seed Scripts

Populates all databases with sample data from `common_seed.json`.

## Prerequisites

- Docker containers must be running (`docker compose up -d`)
- No local Python dependencies needed — scripts run inside the service containers

## Usage

Run from the `backend/` directory:

```bash
bash seed_scripts/seed_all.sh
```

This uses `docker compose exec` to run each script inside its service container (which already has the correct Python packages and `dbURL` env var). Scripts run in dependency order:

| Order | Script | Database | Depends on |
|-------|--------|----------|------------|
| 1 | `doctor_seed.py` | `doctor_db` | — |
| 2 | `patient_seed.py` | `patient_db` | — |
| 3 | `inventory_seed.py` | `inventory_db` | — |
| 4 | `appointment_seed.py` | `appointment_db` | doctors, patients |
| 5 | `invoice_seed.py` | `invoice_db` | appointments |
| 6 | `delivery_seed.py` | `delivery_db` | appointments |


## Seed Data

All scripts read from `common_seed.json`, which contains:

- 2 doctors
- 2 patients
- 5 appointments
- 4 invoices
- 2 deliveries
- 3 medicines + 2 reservations
