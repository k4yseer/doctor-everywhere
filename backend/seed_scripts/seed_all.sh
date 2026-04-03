#!/usr/bin/env bash
set -euo pipefail

# Run all seed scripts inside their respective Docker containers.
# The containers already have the correct dbURL env vars and Python packages.
# Usage: bash seed_scripts/seed_all.sh   (from the backend/ directory)

COMPOSE_PREFIX="backend"
SEED_DIR="/usr/src/app/seed_scripts"

echo "=== Seeding Doctor DB ==="
docker exec "${COMPOSE_PREFIX}-doctor-service-1" python "${SEED_DIR}/doctor_seed.py"

echo "=== Seeding Appointment DB ==="
docker exec "${COMPOSE_PREFIX}-appointment-service-1" python "${SEED_DIR}/appointment_seed.py"

echo "=== Seeding Patient DB ==="
docker exec "${COMPOSE_PREFIX}-patient-service-1" python "${SEED_DIR}/patient_seed.py"

echo "=== Seeding Invoice DB ==="
docker exec "${COMPOSE_PREFIX}-invoice-service-1" python "${SEED_DIR}/invoice_seed.py"

echo "=== Seeding Inventory DB ==="
docker exec "${COMPOSE_PREFIX}-inventory-service-1" python "${SEED_DIR}/inventory_seed.py"

echo "=== Seeding Delivery DB ==="
docker exec "${COMPOSE_PREFIX}-delivery-service-1" python "${SEED_DIR}/delivery_seed.py"

echo ""
echo "All databases seeded successfully!"
