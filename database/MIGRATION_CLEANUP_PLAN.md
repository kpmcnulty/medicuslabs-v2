# Migration Cleanup Plan

## Current Migration Conflicts

We have multiple migrations trying to do similar things:
- **006_add_disease_specific_sources.sql** - Adds sources for non-existent diseases
- **006_rename_reddit_source.sql** - Small rename operation
- **007_add_source_association_method.sql** - Adds association_method with 'fixed'
- **007_simplify_source_configs.sql** - Changes to 'linked' and adds search_terms
- **008_update_reddit_sources.sql** - Complex Reddit config
- **008_update_association_constraint.sql** - Fixes constraint
- **009_simplify_and_cleanup.sql** - Our new comprehensive cleanup

## Recommended Action

### Option 1: Clean Slate (Recommended for Development)
```bash
# 1. Drop and recreate database
make down
make clean

# 2. Remove conflicting migrations
rm database/migrations/006_add_disease_specific_sources.sql
rm database/migrations/007_add_source_association_method.sql  
rm database/migrations/008_update_reddit_sources.sql

# 3. Rename our cleanup to be the next migration
mv database/migrations/009_simplify_and_cleanup.sql database/migrations/006_complete_simplification.sql

# 4. Start fresh
make up
```

### Option 2: Fix Existing (For Production)
Run the migrations in this order:
1. 008_update_association_constraint.sql
2. 009_simplify_and_cleanup.sql

Then manually verify the state.

## Final Migration Structure

After cleanup, migrations should be:
1. **001_complete_schema.sql** - Base schema
2. **002_seed_data.sql** - Remove disease inserts from here
3. **003_fix_schema_and_add_config.sql** - Schema fixes
4. **004_add_missing_columns.sql** - Additional columns
5. **005_add_reddit_config.sql** - Reddit configuration
6. **006_complete_simplification.sql** - Our new simplified setup

## Key Changes Made

1. ✅ Removed sources for non-existent diseases
2. ✅ Consolidated to 4 core sources
3. ✅ Fixed association_method values ('linked' vs 'search')
4. ✅ Removed default_config column
5. ✅ Added search_terms to all diseases
6. ✅ Cleaned up orphaned data