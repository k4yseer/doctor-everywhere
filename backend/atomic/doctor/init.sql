-- =============================================================
-- Doctor Service - docker-entrypoint-initdb.d bootstrap script
-- =============================================================

CREATE DATABASE IF NOT EXISTS doctor_db;
USE doctor_db;

-- ------------------------------------------------------------
-- Table: doctors
-- Matches SQLAlchemy model: Doctor
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS doctors (
    id        INT                                NOT NULL AUTO_INCREMENT,
    name      VARCHAR(128)                       NOT NULL,
    specialty VARCHAR(128)                       NOT NULL,
    status    ENUM('AVAILABLE','UNAVAILABLE')    NOT NULL DEFAULT 'AVAILABLE',
    PRIMARY KEY (id)
);

-- ------------------------------------------------------------
-- Seed data
-- ------------------------------------------------------------
INSERT INTO doctors (name, specialty, status) VALUES
    ('Dr. Alice Chen', 'Cardiology', 'AVAILABLE'),
    ('Dr. Bob Tan', 'Dermatology', 'AVAILABLE');
