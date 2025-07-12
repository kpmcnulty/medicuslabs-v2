-- Migration: Update association_method constraint to use 'linked' instead of 'fixed'

-- First, update any existing 'fixed' values to 'linked'
UPDATE sources SET association_method = 'linked' WHERE association_method = 'fixed';

-- Drop the old constraint
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_association_method_check;
ALTER TABLE sources DROP CONSTRAINT IF EXISTS check_association_method;

-- Add the new constraint with correct values
ALTER TABLE sources ADD CONSTRAINT sources_association_method_check 
    CHECK (association_method IN ('linked', 'search'));

-- Update the comment to reflect the new terminology
COMMENT ON COLUMN sources.association_method IS 'How this source relates to diseases: linked = fixed to specific diseases, search = searches for disease terms';