-- Add 'safety' as a valid category for sources
ALTER TABLE sources 
DROP CONSTRAINT sources_category_check;

ALTER TABLE sources 
ADD CONSTRAINT sources_category_check 
CHECK (category IN ('publications', 'trials', 'community', 'safety'));