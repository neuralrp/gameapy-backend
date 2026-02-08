# Gameapy Database Migrations

## Running Migrations

### Apply Phase 1 Migration:
```bash
cd backend
python migrations/001_phase1_schema.py
```

### Check Migration Status:
```bash
sqlite3 gameapy.db
.schema character_cards  # Verify new columns
.schema self_cards       # Should exist after Phase 1
.schema world_events     # Should exist after Phase 1
SELECT * FROM migration_history;  # View applied migrations
.quit
```

## Migration History

| ID  | Name              | Applied | Description                           |
|-----|-------------------|---------|---------------------------------------|
| 001 | phase1_schema.py  | TBD     | Adds self_cards, world_events, entity tracking |

## Rollback

⚠️ **Migrations are forward-only**. Always backup database before applying:
```bash
cp backend/gameapy.db backend/gameapy.db.backup
```

## Adding New Migrations

1. Create `backend/migrations/00X_migration_name.py`
2. Add entry to `migration_history` table (handled automatically)
3. Update this README with migration details

## Migration Conventions

- Each migration script should have a unique 3-digit ID (001, 002, etc.)
- Use `migration_tracker` functions to check if migration is already applied
- Always wrap changes in transactions with rollback on error
- Record successful migrations in `migration_history`
- Test migrations on a backup database before production

## Development

### Seed Test Data:
```bash
cp backend/gameapy.db backend/gameapy_test.db
python backend/migrations/seed_test_data.py
```

⚠️ **Never run seed_test_data.py on production database**
