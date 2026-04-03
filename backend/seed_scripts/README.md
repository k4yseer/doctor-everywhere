# Seed Scripts

Populates all databases with sample data from `common_seed.json`.

## Prerequisites

- Python 3 with `sqlalchemy`, `pymysql`, and `mysql-connector-python` installed
- MySQL running with the databases already created (`doctor_db`, `patient_db`, `inventory_db`, `appointment_db`, `invoice_db`, `delivery_db`)

## Usage

Run from the `backend/` directory:

```bash
bash seed_scripts/seed_all.sh
```

This runs all scripts in dependency order:

| Order | Script | Database | Depends on |
|-------|--------|----------|------------|
| 1 | `doctor_seed.py` | `doctor_db` | — |
| 2 | `patient_seed.py` | `patient_db` | — |
| 3 | `inventory_seed.py` | `inventory_db` | — |
| 4 | `appointment_seed.py` | `appointment_db` | doctors, patients |
| 5 | `invoice_seed.py` | `invoice_db` | appointments |
| 6 | `delivery_seed.py` | `delivery_db` | appointments |

## Custom DB Connection

Each script defaults to `root:root@localhost:3306`. Override with the `dbURL` environment variable:

```bash
dbURL="mysql+pymysql://user:password@host:3306/doctor_db" python seed_scripts/doctor_seed.py
```

Or set it for the entire run:

```bash
export DB_SERVER=localhost DB_PORT=3306 DB_USER=root DB_PASSWORD=root
bash seed_scripts/seed_all.sh
```

## Seed Data

All scripts read from `common_seed.json`, which contains:

- 2 doctors
- 2 patients
- 5 appointments
- 4 invoices
- 2 deliveries
- 3 medicines + 2 reservations
