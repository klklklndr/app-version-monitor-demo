# App Version Monitor

A lightweight GitHub Actions demo that checks Android and iOS app versions and sends an email alert when a new version is detected.

This is a clean public demo repository. It does not include real client app identifiers, credentials, or production version records.

## What it does

- Checks Android app version from Google Play
- Checks iOS app version from the App Store Lookup API
- Compares the latest version with the stored version record
- Sends an email alert when a new version is detected
- Updates a runtime version record through GitHub Actions

## Setup

Configure the required values under GitHub Actions secrets/variables in the repository settings.

Required values:

| Name | Description | Demo example |
|---|---|---|
| `PACKAGE_NAME` | Android package name | `com.example.app` |
| `IOS_BUNDLE_ID` | iOS bundle ID or App Store ID | `1234567890` |
| `EMAIL_SENDER` | Sender email address | `sender@example.com` |
| `EMAIL_PASSWORD` | Email app password or SMTP password | Use repository secret only |
| `EMAIL_RECIPIENT` | Recipient email address | `recipient@example.com` |

At least one of `PACKAGE_NAME` or `IOS_BUNDLE_ID` is required.

Optional values:

| Name | Default |
|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `PLAY_LANG` | `en` |

## Manual test

1. Open the **Actions** tab.
2. Select **App Version Monitor**.
3. Click **Run workflow**.
4. Check the workflow logs.

## Schedule

The workflow runs every 30 minutes by default.

To change the schedule, edit:

```text
.github/workflows/monitor.yml
```

## Demo version record

This repo includes:

```text
version_record.example.json
```

The runtime file is:

```text
version_record.json
```

The runtime file is intentionally ignored in this public demo setup.

## Local test

```bash
pip install -r requirements.txt
python monitor.py
```

For local runs, export the same environment variables that are used by GitHub Actions.

## Notes

- Do not commit real credentials.
- Do not commit real client app identifiers to a public demo repo.
- Keep sensitive values in GitHub Actions secrets.
- Use the example version record only for documentation.

## License

MIT
