-- setup_database.sql
CREATE DATABASE IF NOT EXISTS search_engine_db;
USE search_engine_db;

CREATE TABLE IF NOT EXISTS pages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url VARCHAR(255) UNIQUE NOT NULL,
    content TEXT,
    pagerank_score FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_page_id INT NOT NULL,
    target_page_id INT NOT NULL,
    FOREIGN KEY (source_page_id) REFERENCES pages(id) ON DELETE CASCADE,
    FOREIGN KEY (target_page_id) REFERENCES pages(id) ON DELETE CASCADE
);