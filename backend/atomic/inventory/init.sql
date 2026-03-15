-- ==================================================================
-- Inventory Service — docker-entrypoint-initdb.d bootstrap script
-- ==================================================================

CREATE DATABASE IF NOT EXISTS inventory_db;
USE inventory_db;

-- ------------------------------------------------------------
-- Table: medicine
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicine (
    medicine_code    VARCHAR(50)  NOT NULL,
    medicine_name    VARCHAR(255) NOT NULL,
    stock_available  INT          NOT NULL DEFAULT 0,
    unit_price       DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    PRIMARY KEY (medicine_code)
);

-- ------------------------------------------------------------
-- Table: reservations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id  INT          NOT NULL AUTO_INCREMENT,
    medicine_code   VARCHAR(50)  NOT NULL,
    appointment_id  INT          NOT NULL,
    amount          INT          NOT NULL,
    PRIMARY KEY (reservation_id),
    FOREIGN KEY (medicine_code) REFERENCES medicine(medicine_code)
);

-- ------------------------------------------------------------
-- Seed data
-- ------------------------------------------------------------
INSERT INTO medicine (medicine_code, medicine_name, stock_available, unit_price) VALUES
    ('MED-001', 'Paracetamol 500mg', 100, 1.50),
    ('MED-002', 'Amoxicillin 250mg', 50,  0.80),
    ('MED-003', 'Ibuprofen 400mg',   75,  1.20);
