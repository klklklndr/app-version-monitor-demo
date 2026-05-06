# Quickstart

## 1) Clone and enter repo

```bash
git clone <your-repo-url>
cd app-version-monitor
```

## 2) Create environment file

```bash
cp .env.example .env
```

Bu repoda demo paylaşım standardı olarak değerleri öncelikle **GitHub Actions > Secrets and variables** alanına ekleyin (lokalde çalıştıracaksanız aynı değerleri `.env` içinde de kullanabilirsiniz).

## 3) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4) Prepare local version store

```bash
cp version_record.example.json version_record.json
```

## 5) Run monitor

```bash
set -a
source .env
set +a
python monitor.py
```

## 6) Configure GitHub Actions (demo sharing)

Set these in repository settings:

- **Variables:** `PACKAGE_NAME`/`PACKAGE_NAMES`, `IOS_BUNDLE_ID`, `EMAIL_RECIPIENT`, `SMTP_SERVER`, `SMTP_PORT`, `PLAY_LANG`
- **Secrets:** `EMAIL_SENDER`, `EMAIL_PASSWORD`

Then run **Actions → App Version Monitor → Run workflow**.
