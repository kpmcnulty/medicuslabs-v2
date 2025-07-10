-- Initialize seed data for medical data aggregation platform
-- Run this after the main database schema to populate initial data

-- Load sources
\i seeds/sources.sql

-- Load diseases
\i seeds/diseases.sql