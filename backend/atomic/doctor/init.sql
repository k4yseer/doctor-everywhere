-- =============================================================
-- Doctor Service — docker-entrypoint-initdb.d bootstrap script
-- =============================================================

CREATE DATABASE IF NOT EXISTS doctor_db;
USE doctor_db;

-- ------------------------------------------------------------
-- Table: doctors
-- Matches SQLAlchemy model: Doctor
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS doctors (
    id        INT          NOT NULL AUTO_INCREMENT,
    name      VARCHAR(128) NOT NULL,
    specialty VARCHAR(128) NOT NULL,
    PRIMARY KEY (id)
);

-- ------------------------------------------------------------
-- Table: availability
-- Matches SQLAlchemy model: Availability
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS availability (
    id            INT                        NOT NULL AUTO_INCREMENT,
    doctor_id     INT                        NOT NULL,
    slot_datetime DATETIME                   NOT NULL,
    status        ENUM('AVAILABLE','RESERVED') NOT NULL DEFAULT 'AVAILABLE',
    PRIMARY KEY (id),
    CONSTRAINT fk_availability_doctor
        FOREIGN KEY (doctor_id) REFERENCES doctors (id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ------------------------------------------------------------
-- Seed data — 2 doctors, 2 slots each
-- ------------------------------------------------------------
INSERT INTO doctors (name, specialty) VALUES
    ('Dr. Alice Chen', 'Cardiology'),
    ('Dr. Bob Tan',    'Dermatology');

INSERT INTO availability (doctor_id, slot_datetime, status) VALUES
    (1, '2026-03-10 09:00:00', 'AVAILABLE'),
    (1, '2026-03-10 10:00:00', 'AVAILABLE'),
    (2, '2026-03-10 14:00:00', 'AVAILABLE'),
    (2, '2026-03-10 15:00:00', 'AVAILABLE');
