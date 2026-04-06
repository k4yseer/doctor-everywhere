CREATE DATABASE IF NOT EXISTS delivery_db;
USE delivery_db;
 
CREATE TABLE IF NOT EXISTS delivery (
    delivery_id      VARCHAR(36)  PRIMARY KEY,
    appointment_id   INT  NOT NULL,
    patient_address  VARCHAR(255) NOT NULL,
    tracking_number  VARCHAR(100),
    delivery_status  VARCHAR(20)  NOT NULL DEFAULT 'PENDING'
);