#!/bin/bash
# Run from the backend/ directory: bash seed_scripts/seed_all.sh

set -e

python seed_scripts/doctor_seed.py && python seed_scripts/patient_seed.py && python seed_scripts/inventory_seed.py && python seed_scripts/appointment_seed.py && python seed_scripts/invoice_seed.py && python seed_scripts/delivery_seed.py

echo "All seed scripts completed."
