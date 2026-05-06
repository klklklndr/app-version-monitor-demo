# App Version Monitor (Demo-Ready)

This repository is prepared for **copy-paste setup + immediate run** by anyone who clones it.

It checks Android/iOS app versions and sends an email when a version changes.

## Features

- Android version check (Play Store web + `google-play-scraper` fallback)
- iOS version check (Apple iTunes Lookup API)
- Multi-app iOS support (`IOS_BUNDLE_ID` accepts comma/semicolon separated IDs)
- Version state persistence in JSON
- Email notifications via SMTP
- Scheduled + manual execution with GitHub Actions

## Repository Layout

- `monitor.py` → main script
- `.github/workflows/monitor.yml` → automation
- `.env.example` → environment template
- `version_record.example.json` → safe template state
- `version_record.json` → runtime state file (gitignored)
- `QUICKSTART.md` → 5-minute setup

## 1) Local run (recommended first)

```bash
git clone <your-repo-url>
cd app-version-monitor
cp .env.example .env
cp version_record.example.json version_record.json
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a && source .env && set +a
python monitor.py
```

## 2) Required Environment Variables

At least one app identifier is required:

- `PACKAGE_NAME` (single Android package) **or** `PACKAGE_NAMES` (comma/semicolon separated multiple Android packages)
- `IOS_BUNDLE_ID` (bundle id or numeric App Store ID; comma/semicolon separated multiple iOS apps supported)

Email settings are required:

- `EMAIL_SENDER`
- `EMAIL_PASSWORD`
- `EMAIL_RECIPIENT`

Optional:

- `SMTP_SERVER` (default: `smtp.gmail.com`)
- `SMTP_PORT` (default: `587`)
- `PLAY_LANG` (default: `en`)
- `VERSION_STORAGE_DIR` (default: script directory)

## 3) GitHub Actions setup

In **Settings → Secrets and variables → Actions**:

### Variables
- `PACKAGE_NAME` and/or `PACKAGE_NAMES`
- `IOS_BUNDLE_ID`
- `EMAIL_RECIPIENT`
- `SMTP_SERVER`
- `SMTP_PORT`
- `PLAY_LANG`

### Secrets
- `EMAIL_SENDER`
- `EMAIL_PASSWORD`

Then run:

- **Actions** → **App Version Monitor** → **Run workflow**

## 4) Demo safety

This repository is formatted for public/demo sharing:

- No real credentials in git
- No real client identifiers required in tracked files
- Runtime artifacts are ignored via `.gitignore`

## 5) Troubleshooting

- If Android fetch fails, verify package name and region/lang.
- If iOS lookup fails, test with numeric App Store ID.
- If email fails, verify SMTP host/port and app password policy.

## License

MIT
