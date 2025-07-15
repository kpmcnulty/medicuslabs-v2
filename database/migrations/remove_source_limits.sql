-- Remove the limit columns we just added - we want ALL data!
ALTER TABLE sources 
DROP COLUMN IF EXISTS daily_limit,
DROP COLUMN IF EXISTS weekly_limit;