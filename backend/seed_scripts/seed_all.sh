#!/bin/bash
# Run from the backend/ directory: bash seed_scripts/seed_all.sh

set -e

docker compose exec doctor-service python seed_scripts/doctor_seed.py && \
docker compose exec patient-service python seed_scripts/patient_seed.py && \
docker compose exec inventory-service python seed_scripts/inventory_seed.py && \
docker compose exec appointment-service python seed_scripts/appointment_seed.py && \
docker compose exec invoice-service python seed_scripts/invoice_seed.py && \
docker compose exec delivery-service python seed_scripts/delivery_seed.py

echo "All seed scripts completed."
