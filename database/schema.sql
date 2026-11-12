-- ============================================================
--  Lead Management System — Database Schema (MySQL)
--  Step 1 of the build: Database Design
--
--  This file creates the database and the TWO tables the
--  system needs:
--    1. clients  -> the businesses who log in to see their leads
--    2. leads    -> the form submissions that belong to a client
--
--  How to run this file (from a terminal):
--    mysql -u root -p < database/schema.sql
--  (You will be asked for the MySQL root password.)
-- ============================================================


-- ------------------------------------------------------------
-- 0. Create the database itself, then switch into it.
--    utf8mb4 = full Unicode support (emojis, all languages).
-- ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS leadsdb
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE leadsdb;


-- ------------------------------------------------------------
-- 1. clients
--    One row per business/customer that can log into the
--    dashboard. The `email` column is ALSO the address we
--    send new-lead email notifications to (see Step 9).
--    `password_hash` NEVER stores the plain password — only
--    a bcrypt hash (handled later in auth.py).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients (
    id            INT AUTO_INCREMENT PRIMARY KEY,          -- INTERNAL pk, never exposed
    uuid          CHAR(36) NOT NULL UNIQUE DEFAULT (UUID()), -- PUBLIC id, the only one we send out
    name          VARCHAR(255) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,   -- login id + notification address
    password_hash VARCHAR(255) NOT NULL,          -- bcrypt hash, never plain text
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ------------------------------------------------------------
-- 2. leads
--    One row per contact-form submission. Each lead belongs to
--    exactly ONE client via `client_id` (the foreign key).
--    This is what guarantees one client can never see another
--    client's leads.
--
--    status: a lead starts as 'new', then moves to 'contacted'
--            or 'closed' as the client works it.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    client_id    INT NOT NULL,
    name         VARCHAR(255),
    email        VARCHAR(255),
    phone        VARCHAR(50),
    message      TEXT,
    status       ENUM('new', 'contacted', 'closed') NOT NULL DEFAULT 'new',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Link every lead to its owning client. If someone tries to
    -- insert a lead for a client_id that does not exist, MySQL
    -- rejects it.
    FOREIGN KEY (client_id) REFERENCES clients(id),

    -- Indexes = make the common queries fast.
    -- We filter leads by client_id on EVERY dashboard request,
    -- and we often filter/sort by status.
    INDEX idx_leads_client_id (client_id),
    INDEX idx_leads_status (status)
);


-- ------------------------------------------------------------
-- Quick sanity check after running this file:
--    USE leadsdb;
--    SHOW TABLES;          -- should list: clients, leads
--    DESCRIBE clients;     -- shows the columns
--    DESCRIBE leads;       -- shows the columns
-- ------------------------------------------------------------
