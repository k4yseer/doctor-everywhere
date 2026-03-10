-- ==================================================================
-- Invoice Service — docker-entrypoint-initdb.d bootstrap script
-- ==================================================================

CREATE DATABASE IF NOT EXISTS invoice_db;
USE invoice_db;

-- ------------------------------------------------------------
-- Table: invoices
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id VARCHAR(64) NOT NULL,
    appointment_id VARCHAR(64) NOT NULL,
    patient_id VARCHAR(64) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    payment_status VARCHAR(32) NOT NULL,
    stripe_charge_id VARCHAR(128),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (invoice_id)
);
