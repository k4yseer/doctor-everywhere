-- ==================================================================
-- Appointment Service — docker-entrypoint-initdb.d bootstrap script
-- ==================================================================

CREATE DATABASE IF NOT EXISTS appointment_db;
USE appointment_db;

-- ------------------------------------------------------------
-- Table: appointments
-- Matches SQLAlchemy model: Appointment
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appointments (
    id            INT                                       NOT NULL AUTO_INCREMENT,
    patient_id    INT                                       NOT NULL,
    doctor_id     INT                                       NOT NULL,
    slot_datetime DATETIME                                  NOT NULL,
    meet_link     VARCHAR(512)                              NULL,
    status        ENUM('CONFIRMED','PENDING_PAYMENT','PAID','NO_SHOW') NOT NULL DEFAULT 'CONFIRMED',
    PRIMARY KEY (id)
);

-- ------------------------------------------------------------
-- Seed data — 2 appointments for testing
-- flow: CONFIRMED -> PENDING_PAYMENT (post-consult) -> PAID
-- ------------------------------------------------------------
INSERT INTO appointments (patient_id, doctor_id, slot_datetime, meet_link, status) VALUES
    (1, 1, '2026-03-10 09:00:00', 'https://meet.example.com/abc-111', 'CONFIRMED'),
    (2, 2, '2026-03-10 14:00:00', 'https://meet.example.com/xyz-222', 'PENDING_PAYMENT');
