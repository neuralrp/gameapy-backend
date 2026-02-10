# Gameapy Database Migrations

## Automatic Migration Runner

Migrations are **automatically run on app startup**. No manual intervention required.

When you deploy (locally, Railway, or anywhere else), the app will:
1. Check which migrations have already been applied
2. Run any pending migrations in order
3. Skip migrations that are already applied

### How It Works

The migration system lives in `migrations/run_migrations.py`:
- Tracks all migrations in `migration_history` table
- Automatically applies pending migrations on startup
- Safe to run multiple times (idempotent)

### Adding New Migrations

To add a new migration:

1. Create `backend/migrations/00X_migration_name.py`
2. Add entry to `MIGRATIONS` list in `migrations/run_migrations.py`:
   ```python
   {
       "id": "006",
       "name": "my_migration",
       "module": "migrations.006_my_migration",
       "function": "migrate"  # or your function name
   }
   ```
3. Push to GitHub - migration will run automatically on next deployment

### Running Migrations Manually (Optional)

If you need to run migrations manually:

```bash
cd backend
python migrations/run_migrations.py
```

### Check Migration Status:
```bash
sqlite3 gameapy.db
SELECT * FROM migration_history;  # View applied migrations
.quit
```

## Migration History

| ID  | Name              | Description                           |
|-----|-------------------|---------------------------------------|
| 001 | phase1_schema.py  | Adds self_cards, world_events, entity tracking |
| 004 | pivot_cleanup.py  | Adds is_pinned columns, removes canon law dependencies |
| 005 | add_hidden_flag.py | Adds is_hidden flag to counselor_profiles |

## Rollback

⚠️ **Migrations are forward-only**. Always backup database before applying:
```bash
cp backend/gameapy.db backend/gameapy.db.backup
```

## Migration Conventions

- Each migration script should have a unique 3-digit ID (001, 002, etc.)
- Add entry to `MIGRATIONS` list in `run_migrations.py`
- Always wrap changes in transactions with rollback on error
- Test migrations on a backup database before production

## Development

### Seed Test Data:
```bash
cp backend/gameapy.db backend/gameapy_test.db
python backend/migrations/seed_test_data.py
```

⚠️ **Never run seed_test_data.py on production database**
