# Railway Persistent Volume Setup Guide

This guide explains how to set up a persistent volume on Railway to ensure your database (and character cards) survive deployments.

## Prerequisites

- Railway CLI installed: `npm install -g @railway/cli`
- Railway account logged in: `railway login`
- Project already deployed to Railway

## Why This Is Needed

By default, Railway uses **ephemeral storage** - every deployment creates a fresh container and wipes the filesystem. This means your `gameapy.db` (containing character cards) gets deleted on each deployment.

**Solution:** Use a Railway Persistent Volume that survives deployments.

---

## Step 1: Verify Current Project

```bash
# List your projects
railway projects

# Select your gameapy-backend project
railway project select <project-id>

# Verify the backend service is running
railway status
```

---

## Step 2: Create a Persistent Volume

```bash
# Create a new volume named "gameapy-data"
railway volumes create gameapy-data
```

You should see output like:
```
Creating volume gameapy-data...
Volume created with id: <volume-id>
```

---

## Step 3: Connect Volume to Backend Service

First, find your backend service ID:

```bash
# List all services in the project
railway services
```

You'll see output like:
```
Service: gameapy-backend
  ID: <service-id>
  Project: <project-id>
```

Now connect the volume:

```bash
# Connect volume to backend service
railway volumes connect gameapy-data <service-id> --path /app/data
```

This command:
- Connects the `gameapy-data` volume to your backend service
- Mounts the volume at `/app/data` inside the container
- Sets `RAILWAY_VOLUME_MOUNT_PATH=/app/data` as an environment variable (automatic)

---

## Step 4: Verify Volume Configuration

```bash
# Check environment variables (look for RAILWAY_VOLUME_MOUNT_PATH)
railway variables

# Check volume details
railway volumes
```

You should see `RAILWAY_VOLUME_MOUNT_PATH=/app/data` in the variables list.

---

## Step 5: Deploy Updated Code

Your code changes are already in the repo. Just push:

```bash
cd backend
git add .
git commit -m "feat: Add Railway persistent volume support"
git push origin main
```

Railway will automatically detect the push and redeploy.

---

## Step 6: Verify Database Persistence

### Check Logs for Database Path

```bash
# Stream logs in real-time
railway logs

# Or view recent logs
railway logs --tail 50
```

Look for this log line:
```
[INFO] Database path: /app/data/gameapy.db
```

**Important:** If you see `Database path: gameapy.db` (without `/app/data/`), the volume is NOT mounted correctly. Go back to Step 3.

### Test Persistence

1. Open your web app: https://gameapy-web.vercel.app
2. Create a test character card (e.g., "Test Person")
3. Push a small code change to trigger new deployment:
   ```bash
   echo "# test" >> backend/README.md
   git add backend/README.md
   git commit -m "test: trigger deployment"
   git push origin main
   ```
4. Wait for deployment to complete (check logs: `railway logs`)
5. Open the web app again
6. Verify "Test Person" card still exists ✅

---

## Troubleshooting

### Issue: Database still uses ephemeral storage

**Symptom:** Logs show `Database path: gameapy.db` instead of `/app/data/gameapy.db`

**Solution:**
1. Verify volume is connected: `railway volumes`
2. Check environment variable: `railway variables` (look for `RAILWAY_VOLUME_MOUNT_PATH`)
3. If missing, reconnect volume: `railway volumes connect gameapy-data <service-id> --path /app/data`
4. Redeploy: `railway up`

### Issue: Database directory doesn't exist

**Symptom:** Logs show `[INFO] Created database directory: /app/data` but database fails to initialize

**Solution:**
1. The code automatically creates the directory (see `database.py` lines 25-28)
2. If it fails, check volume permissions in Railway dashboard
3. May need to add `RAILWAY_RUN_UID=0` environment variable (Railway Pro feature)

### Issue: Old data lost after switch

**Expected behavior:** When switching from ephemeral storage to volumes, the old database is wiped.

**Solution:**
- This is a one-time migration cost
- New data will persist going forward
- Consider this a fresh start with persistent storage

### Issue: Volume not writable

**Symptom:** Database creation fails with permission error

**Solution:**
1. Set `RAILWAY_RUN_UID=0` environment variable (run as root):
   ```bash
   railway variables set RAILWAY_RUN_UID=0
   railway up
   ```
2. This is only needed if Railway uses a non-root user by default

---

## Railway CLI Commands Reference

| Command | Purpose |
|---------|---------|
| `railway login` | Login to Railway account |
| `railway projects` | List all projects |
| `railway project select <id>` | Select active project |
| `railway services` | List services in project |
| `railway volumes` | List volumes in project |
| `railway volumes create <name>` | Create new volume |
| `railway volumes connect <vol> <svc> --path <path>` | Connect volume to service |
| `railway variables` | List environment variables |
| `railway variables set <key>=<val>` | Set environment variable |
| `railway up` | Deploy current directory |
| `railway logs` | View service logs |
| `railway status` | Check service status |
| `railway open` | Open service in browser |

---

## How It Works (Technical Details)

### Code Changes

1. **`app/core/config.py`**: Detects `RAILWAY_VOLUME_MOUNT_PATH` env variable
2. **`app/db/database.py`**: Uses configured path instead of hardcoded `"gameapy.db"`
3. **`railway.json`**: Documents Railway configuration (optional)

### Path Resolution Logic

```python
# Priority order:
if DATABASE_PATH env variable:
    use DATABASE_PATH
elif RAILWAY_VOLUME_MOUNT_PATH env variable (auto-injected by Railway):
    use RAILWAY_VOLUME_MOUNT_PATH + "/gameapy.db"
else:
    use "gameapy.db" (local development)
```

### Database Path by Environment

| Environment | Database Path |
|------------|---------------|
| Local Development | `gameapy.db` (current directory) |
| Railway (with volume) | `/app/data/gameapy.db` (persistent volume) |
| Railway (without volume) | `gameapy.db` (ephemeral - NOT recommended) |

---

## Monitoring & Backups

### Check Volume Usage

```bash
# Volume details
railway volumes inspect gameapy-data
```

### Manual Backup

You can SSH into the container and export the database:

```bash
# Open Railway shell
railway shell

# Inside container, export database
sqlite3 /app/data/gameapy.db .dump > /app/data/backup_$(date +%Y%m%d).sql

# Copy backup to local machine
railway cp /app/data/backup_20240211.sql ./backup.sql
```

### Automatic Backups (Railway Pro)

Railway Pro supports automatic volume backups. Enable in Railway dashboard:
1. Go to volume settings
2. Enable "Automatic Backups"
3. Set retention policy (e.g., 7 days)

---

## Summary

✅ Code changes implemented and tested
✅ Ready for Railway volume setup
⚠️ Current Railway data will be lost (one-time migration)
✅ New data will persist across deployments after setup

**Next Steps:**
1. Run `railway volumes create gameapy-data`
2. Run `railway volumes connect gameapy-data <service-id> --path /app/data`
3. Push code changes to trigger deployment
4. Verify logs show `Database path: /app/data/gameapy.db`
5. Test persistence with a test card

---

## Additional Resources

- Railway Volumes Documentation: https://docs.railway.app/guides/volumes
- Railway CLI Reference: https://docs.railway.app/reference/cli
- Railway Dashboard: https://railway.app/project/<project-id>
