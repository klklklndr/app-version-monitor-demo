# Setup Visual Guide

Use this order when preparing the repository for demos:

1. **Repository files present**
   - `README.md`
   - `QUICKSTART.md`
   - `.env.example`
   - `.github/workflows/monitor.yml`

2. **GitHub Settings → Secrets and variables**
   - Add required values listed in `README.md`.

3. **Actions tab**
   - Open "App Version Monitor"
   - Click "Run workflow"
   - Verify logs

4. **Expected result**
   - If a new app version is detected, an email is sent.
   - `version_record.json` is updated by workflow commit.
