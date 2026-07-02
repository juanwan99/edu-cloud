# edu-cloud local backup automation

This directory contains the minimal local backup automation for edu-cloud. It does not connect to production by itself and it does not store secrets. Operators provide `DATABASE_URL` at runtime through the environment or an uncommitted environment file.

## Script

Run from the repository root:

```bash
python deploy/backup/edu-cloud-backup.py --target-dir /var/backups/edu-cloud
```

Required inputs:

- `DATABASE_URL`: `sqlite:///path/to/edu_cloud.db`, `postgresql://...`, or `postgres://...`.
- `--target-dir` or `EDU_CLOUD_BACKUP_DIR`: an existing local directory.

Optional inputs:

- `--mode auto|sqlite|postgresql`: defaults to `auto` and must match `DATABASE_URL` when set.
- `--pg-dump-bin`: PostgreSQL dump executable, defaults to `pg_dump`.
- `PG_DUMP_BIN`: environment equivalent for `--pg-dump-bin`.

The script fails loudly when required configuration is missing, the target directory does not exist, the SQLite file is missing, or `pg_dump` cannot be found. It never silently creates a backup directory.

## SQLite file backup

For local SQLite:

```bash
DATABASE_URL=sqlite:////home/ops/projects/edu-cloud/edu_cloud.db \
python deploy/backup/edu-cloud-backup.py --target-dir /home/ops/backups/edu-cloud
```

The script copies the SQLite file into the target directory with a UTC timestamped filename. If `-wal` or `-shm` sidecar files are present, they are copied next to the main backup file.

## PostgreSQL pg_dump backup

For PostgreSQL:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/edu_cloud \
python deploy/backup/edu-cloud-backup.py --target-dir /home/ops/backups/edu-cloud
```

PostgreSQL mode requires a local `pg_dump` binary. The resulting dump uses `pg_dump --format=custom --no-owner`. The script does not print `DATABASE_URL` on success.

## systemd example

The files in `deploy/systemd/` are examples:

- `edu-cloud-backup.service` runs one backup and expects `/home/ops/backups/edu-cloud` to exist.
- `edu-cloud-backup.timer` runs the service daily with a randomized delay.

Install them only after reviewing paths for the host:

```bash
sudo install -m 0644 deploy/systemd/edu-cloud-backup.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/edu-cloud-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now edu-cloud-backup.timer
```

Use `systemctl status edu-cloud-backup.service` and the configured log file to verify results. Do not commit environment files, database URLs with passwords, backup dumps, or production host details.
