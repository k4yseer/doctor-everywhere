CREATE DATABASE IF NOT EXISTS error_db;
USE error_db;

CREATE TABLE IF NOT EXISTS error (
    error_id          VARCHAR(36)  PRIMARY KEY,
    timestamp         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_service    VARCHAR(100) NOT NULL,
    error_code        VARCHAR(50)  NOT NULL,
    error_message     TEXT         NOT NULL,
    payload           TEXT,
    resolution_status VARCHAR(20)  NOT NULL DEFAULT 'UNRESOLVED'
);