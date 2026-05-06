# Implementation Summary

This demo monitors Android and iOS app versions and sends email alerts when versions change.

## Components

- `monitor.py`: Main runtime logic.
- `.github/workflows/monitor.yml`: Scheduled/manual GitHub Actions runner.
- `.env.example`: Shareable template for required configuration.
- `version_record.example.json`: Safe starter state for new clones.

## Version checks

- Android: Web scrape fallback + `google-play-scraper` API.
- iOS: Apple iTunes Lookup API by bundle ID or App Store numeric ID.

## State management

- Runtime state lives in `version_record.json`.
- Public-safe starter state lives in `version_record.example.json`.

## Demo-safe defaults

- No real app IDs or emails committed.
- Runtime files ignored by git.
