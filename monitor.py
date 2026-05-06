#!/usr/bin/env python3


import os
import json
import smtplib
import sys
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests

try:
    from google_play_scraper import app
except ImportError:
    print("Error: google_play_scraper not installed. Run: pip install google-play-scraper")
    sys.exit(1)


class VersionMonitor:
    """Monitors Google Play Store for version updates and sends email alerts."""
    
    def __init__(self):
        """Initialize the monitor with environment variables."""
        # Android package names (optional if monitoring iOS only)
        # Supports:
        # - PACKAGE_NAME="com.example.app" (backward compatible)
        # - PACKAGE_NAME="com.app1,com.app2"
        # - PACKAGE_NAMES="com.app1,com.app2"
        android_packages_raw = os.getenv('PACKAGE_NAMES') or os.getenv('PACKAGE_NAME', '')
        self.android_packages: List[str] = [
            p.strip() for p in android_packages_raw.replace(';', ',').split(',') if p.strip()
        ]
        # Backward-compatible primary package alias used in some email subject fallbacks
        self.package_name = self.android_packages[0] if self.android_packages else None
        self.play_lang = os.getenv('PLAY_LANG', 'en')

        # iOS identifiers: support multiple separated by comma/semicolon
        # Can be bundle IDs (e.g., com.example.app) or numeric App Store IDs (e.g., 1460593315)
        ios_ids = os.getenv('IOS_BUNDLE_ID', '')
        self.ios_ids: List[str] = [b.strip() for b in ios_ids.replace(';', ',').split(',') if b.strip()]

        # Email configuration
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        # Support multiple recipients separated by comma or semicolon
        email_recipient_str = os.getenv('EMAIL_RECIPIENT', '')
        self.email_recipients = [e.strip() for e in email_recipient_str.replace(';', ',').split(',') if e.strip()]
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))

        # Storage directory (defaults to script directory) and files
        self.storage_dir = Path(os.getenv('VERSION_STORAGE_DIR', Path(__file__).parent)).expanduser().resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.version_file = self.storage_dir / 'version_record.json'
        self.event_log_file = self.storage_dir / 'version_events.log'

        # Validate required configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate that required environment variables are set.

        At least one of PACKAGE_NAME/PACKAGE_NAMES or IOS_BUNDLE_ID must be provided, plus
        email sender/password/recipient must be configured.
        """
        if not (self.android_packages or self.ios_ids):
            raise ValueError("Missing app identifier: set PACKAGE_NAME/PACKAGE_NAMES and/or IOS_BUNDLE_ID")

        required = {
            'EMAIL_SENDER': self.email_sender,
            'EMAIL_PASSWORD': self.email_password,
            'EMAIL_RECIPIENT': self.email_recipients,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Set them via: export VAR=value (locally) or secrets (GitHub Actions)"
            )

    def fetch_android_version(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest Android version and metadata for the configured package."""

        if not package_name:
            return None

        best_info: Optional[Dict[str, Any]] = None
        best_source: Optional[str] = None
        attempts: List[str] = []

        try:
            print(
                f"[{self._timestamp()}] Fetching Android version for package: {package_name} (lang={self.play_lang})"
            )

            web_version = self._fetch_android_version_via_web(package_name)
            if web_version:
                best_info = {'version': web_version}
                best_source = 'web'
                attempts.append(f"web:{web_version}")
            else:
                attempts.append("web:None")

            scraper_version = self._fetch_android_version_via_scraper(package_name)
            if scraper_version:
                attempts.append(
                    f"scraper:{scraper_version.get('version')}|updated:{scraper_version.get('updated')}"
                )
                scraper_version_value = scraper_version.get('version')
                if scraper_version_value:
                    if best_info is None:
                        best_info = scraper_version
                        best_source = 'scraper'
                    else:
                        trend = self._compare_version_order(scraper_version_value, best_info['version'])
                        if trend == 1:
                            best_info = scraper_version
                            best_source = 'scraper'
            else:
                attempts.append("scraper:None")

            if best_info:
                extra_meta = f", updated={best_info.get('updated')}" if best_info.get('updated') else ''
                print(
                    f"[{self._timestamp()}] Current Android version on Play Store: {best_info['version']} "
                    f"(source={best_source}, attempts={attempts}{extra_meta})"
                )
            else:
                print(f"[{self._timestamp()}] Unable to fetch Android version from web or scraper (attempts={attempts})")

            return best_info
        except Exception as e:
            print(f"[{self._timestamp()}] Error fetching Android version: {e}")
            return None

    def _fetch_android_version_via_scraper(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Fetch Android version using google_play_scraper."""

        try:
            app_data = app(package_name, lang=self.play_lang)
            version = app_data.get('version')
            updated = app_data.get('updated')
            if version:
                if updated:
                    print(
                        f"[{self._timestamp()}] Fetched Android version {version} via scraper "
                        f"(updated={updated})"
                    )
                else:
                    print(f"[{self._timestamp()}] Fetched Android version {version} via scraper")
                return {'version': version, 'updated': updated}
            print(f"[{self._timestamp()}] Scraper returned no version; falling back to web scrape")
        except Exception as inner:
            print(f"[{self._timestamp()}] Error fetching Android version via scraper: {inner}; falling back to web scrape")
        return None

    def _fetch_android_version_via_web(self, package_name: str) -> Optional[str]:
        """Fetch version by scraping the Play Store web page (more closely matches the live site)."""

        url = f"https://play.google.com/store/apps/details?id={package_name}&hl={self.play_lang}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept-Language': f"{self.play_lang};q=0.9",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[{self._timestamp()}] Web scrape failed: {e}")
            return None

        # Try both structured data and visible "Current Version" style labels
        patterns = [
            r'"softwareVersion"\s*:\s*"([^"]+)"',
            r'Current Version\s*</div>\s*<span[^>]*>([^<]+)<',
        ]
        for pattern in patterns:
            match = re.search(pattern, resp.text)
            if match:
                version = match.group(1).strip()
                print(f"[{self._timestamp()}] Fetched Android version {version} via web scrape")
                return version

        print(f"[{self._timestamp()}] Web scrape could not parse version")
        return None

    def fetch_ios_version(self, identifier: str) -> Optional[Dict[str, str]]:
        """Fetch iOS app info via iTunes Lookup API.
        
        Supports both bundle identifiers (e.g., com.example.app) and numeric App Store IDs.

        Returns a dict with keys `version`, `trackViewUrl`, and `trackName` (app name) if found.
        """
        try:
            print(f"[{self._timestamp()}] Fetching iOS version for identifier: {identifier}")
            
            # Determine if it's a numeric App Store ID or bundle ID
            if identifier.isdigit():
                url = f"https://itunes.apple.com/lookup?id={identifier}"
                print(f"[{self._timestamp()}] Using App Store ID lookup")
            else:
                url = f"https://itunes.apple.com/lookup?bundleId={identifier}"
                print(f"[{self._timestamp()}] Using bundle ID lookup")
            
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results', [])
            if not results:
                print(f"[{self._timestamp()}] No iOS app found for identifier: {identifier}")
                return None
            info = results[0]
            version = info.get('version')
            track_url = info.get('trackViewUrl')
            track_name = info.get('trackName', identifier)  # Fallback to identifier if no name
            print(f"[{self._timestamp()}] Current iOS version on App Store: {version}")
            return {'version': version, 'trackViewUrl': track_url, 'trackName': track_name}
        except Exception as e:
            print(f"[{self._timestamp()}] Error fetching iOS version: {e}")
            return None
    
    def _load_store(self) -> Dict[str, Any]:
        """Load the version record file and return a dict (safe)."""
        try:
            if self.version_file.exists():
                with open(self.version_file, 'r') as f:
                    return json.load(f) or {}
        except Exception as e:
            print(f"[{self._timestamp()}] Error reading version file: {e}")
        return {}

    def get_stored_version(self, platform: str, identifier: str) -> Optional[str]:
        """Get stored version for a given platform+identifier key."""
        store = self._load_store()
        # Backwards compatibility: older file may have top-level 'version'
        if 'version' in store and 'package_name' in store and platform == 'android' and store.get('package_name') == identifier:
            return store.get('version')
        key = f"{platform}:{identifier}"
        entry = store.get(key)
        if isinstance(entry, dict):
            return entry.get('version')
        return entry
    
    def store_version(self, platform: str, identifier: str, version: str, extra: Optional[Dict[str, Any]] = None) -> bool:
        """Store a version under a platform:identifier key."""
        try:
            store = self._load_store()
            key = f"{platform}:{identifier}"
            entry: Dict[str, Any] = {'version': version, 'last_updated': self._timestamp(), 'id': identifier}
            if extra:
                entry.update(extra)
            store[key] = entry
            with open(self.version_file, 'w') as f:
                json.dump(store, f, indent=2)
            print(f"[{self._timestamp()}] Stored {platform} version for {identifier}: {version}")
            return True
        except Exception as e:
            print(f"[{self._timestamp()}] Error storing version: {e}")
            return False

    def log_version_change(
        self,
        platform: str,
        identifier: str,
        old_version: str,
        new_version: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a version change event to the log file."""

        try:
            entry = {
                'timestamp': self._timestamp(),
                'platform': platform,
                'identifier': identifier,
                'old_version': old_version,
                'new_version': new_version,
            }
            if extra:
                entry.update(extra)
            with open(self.event_log_file, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[{self._timestamp()}] Logged version change for {platform}:{identifier} → {new_version}")
        except Exception as e:
            print(f"[{self._timestamp()}] Failed to log version change: {e}")

    def log_version_regression(self, platform: str, identifier: str, stored_version: str, current_version: str) -> None:
        """Log when a platform reports a lower version than what is stored."""

        try:
            entry = {
                'timestamp': self._timestamp(),
                'platform': platform,
                'identifier': identifier,
                'stored_version': stored_version,
                'reported_version': current_version,
                'event': 'regression_ignored',
            }
            with open(self.event_log_file, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(
                f"[{self._timestamp()}] Ignoring regression for {platform}:{identifier}: "
                f"stored {stored_version} > reported {current_version}"
            )
        except Exception as e:
            print(f"[{self._timestamp()}] Failed to log version regression: {e}")

    def log_updated_regression(self, platform: str, identifier: str, stored_date: str, current_date: str) -> None:
        """Log when a platform reports an older updated date than what is stored."""

        try:
            entry = {
                'timestamp': self._timestamp(),
                'platform': platform,
                'identifier': identifier,
                'stored_updated': stored_date,
                'reported_updated': current_date,
                'event': 'updated_regression_ignored',
            }
            with open(self.event_log_file, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(
                f"[{self._timestamp()}] Ignoring Android updated regression for {identifier}: "
                f"stored {stored_date} > reported {current_date}"
            )
        except Exception as e:
            print(f"[{self._timestamp()}] Failed to log updated regression: {e}")

    @staticmethod
    def _parse_numeric_version(version: str) -> Optional[List[int]]:
        """Parse dotted numeric versions into integer lists (e.g., '1.2.3' -> [1, 2, 3])."""

        parts = [p for p in version.strip().split('.') if p]
        if parts and all(part.isdigit() for part in parts):
            return [int(part) for part in parts]
        return None

    def _compare_version_order(self, current_version: str, stored_version: str) -> Optional[int]:
        """Compare two versions.

        Returns 1 if current_version is newer, -1 if older, 0 if equal, or None if order is unknown.
        """

        current_parts = self._parse_numeric_version(current_version)
        stored_parts = self._parse_numeric_version(stored_version)
        if current_parts is not None and stored_parts is not None:
            max_len = max(len(current_parts), len(stored_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            stored_parts.extend([0] * (max_len - len(stored_parts)))
            if current_parts > stored_parts:
                return 1
            if current_parts < stored_parts:
                return -1
            return 0
        if current_version == stored_version:
            return 0
        return None

    @staticmethod
    def _compare_date_order(current_date: str, stored_date: str) -> Optional[int]:
        """Compare two ISO-formatted dates (YYYY-MM-DD)."""

        try:
            current = datetime.strptime(current_date, "%Y-%m-%d").date()
            stored = datetime.strptime(stored_date, "%Y-%m-%d").date()
        except Exception:
            return None

        if current > stored:
            return 1
        if current < stored:
            return -1
        return 0

    @staticmethod
    def _normalize_updated_date(updated: Optional[Any]) -> Optional[str]:
        """Normalize Play Store updated field to YYYY-MM-DD when possible."""

        if updated is None:
            return None

        if isinstance(updated, (int, float)):
            try:
                dt = datetime.utcfromtimestamp(int(updated))
                return dt.strftime("%Y-%m-%d")
            except (OverflowError, ValueError, OSError):
                return None

        if not isinstance(updated, str):
            return None

        cleaned = updated.strip()
        if not cleaned:
            return None

        if cleaned.isdigit():
            try:
                dt = datetime.utcfromtimestamp(int(cleaned))
                return dt.strftime("%Y-%m-%d")
            except (OverflowError, ValueError, OSError):
                return None

        patterns = [
            "%B %d, %Y",  # December 20, 2025
            "%b %d, %Y",  # Dec 20, 2025
            "%d %B %Y",   # 20 December 2025
            "%d %b %Y",   # 20 Dec 2025
            "%Y-%m-%d",   # 2025-12-20
        ]

        for fmt in patterns:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", cleaned)
        if match:
            return match.group(0)

        return None
    
    def send_email_alert(
        self,
        old_version: str,
        new_version: str,
        title: Optional[str] = None,
        link: Optional[str] = None,
        subject_platform: Optional[str] = None,
    ) -> bool:
        """
        Send an email notification about the version update.

        Args:
            old_version: Previous version.
            new_version: New version.
            title: Optional display title for the email body.
            link: Optional link to the app store listing.
            subject_platform: Optional platform label for the email subject (e.g., "Android", "iOS").

        Returns:
            True if email sent successfully, False otherwise.
        """
        try:
            print(f"[{self._timestamp()}] Preparing to send email alert...")

            # Create email message
            msg = MIMEMultipart('alternative')
            subject_target = title or (self.package_name or 'App')
            subject_label = subject_platform or 'New Version Alert'
            msg['Subject'] = f"New Version Alert: {subject_label}" if subject_platform else subject_label
            msg['From'] = self.email_sender
            msg['To'] = ', '.join(self.email_recipients)
            
            # Create plain text and HTML versions
            link_text = ''
            if link:
                link_text = f"\nCheck it out:\n{link}\n"

            text = f"""
New Version Detected!

Target: {subject_target}
Previous Version: {old_version}
New Version: {new_version}

Timestamp: {self._timestamp()}
{link_text}
"""

            link_html = ''
            if link:
                link_html = f'<p><a href="{link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View</a></p>'

            html = f"""
<html>
  <body style="font-family: Arial, sans-serif;">
    <h2 style="color: #4CAF50;">🔔 New Version Alert!</h2>
    <p><strong>Target:</strong> {subject_target}</p>
    <p><strong>Previous Version:</strong> <span style="color: #666;">{old_version}</span></p>
    <p><strong>New Version:</strong> <span style="color: #4CAF50; font-size: 1.2em;"><strong>{new_version}</strong></span></p>
    <p><strong>Timestamp:</strong> {self._timestamp()}</p>
    {link_html}
  </body>
</html>
"""
            
            part1 = MIMEText(text, 'plain')
            part2 = MIMEText(html, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email to all recipients
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            
            print(f"[{self._timestamp()}] Email alert sent successfully to {', '.join(self.email_recipients)}")
            return True
            
        except Exception as e:
            print(f"[{self._timestamp()}] Error sending email: {e}")
            return False
    
    def run_check(self) -> bool:
        """
        Execute the version check cycle.
        
        Returns:
            True if check completed successfully, False otherwise.
        """
        print("\n" + "="*60)
        print(f"[{self._timestamp()}] Starting version check cycle...")
        print("="*60)
        
        # Check Android if configured
        any_success = True
        if self.android_packages:
            for package_name in self.android_packages:
                android_info = self.fetch_android_version(package_name)
                if not android_info:
                    print(f"[{self._timestamp()}] Failed to fetch Android version for {package_name}. Skipping.")
                    any_success = False
                    continue

                current_version = android_info.get('version') if isinstance(android_info, dict) else None
                updated_at = android_info.get('updated') if isinstance(android_info, dict) else None
                updated_epoch = None
                if isinstance(updated_at, (int, float)):
                    updated_epoch = int(updated_at)
                elif isinstance(updated_at, str) and updated_at.strip().isdigit():
                    updated_epoch = int(updated_at.strip())
                normalized_updated = self._normalize_updated_date(updated_at)
                if normalized_updated:
                    print(
                        f"[{self._timestamp()}] Parsed Android updated date for {package_name}: {normalized_updated} "
                        f"(raw={updated_at})"
                    )
                if not current_version:
                    print(f"[{self._timestamp()}] Android fetch returned no version string for {package_name}. Skipping.")
                    any_success = False
                    continue

                store = self._load_store()
                store_key = f"android:{package_name}"
                stored_entry = store.get(store_key, {}) if isinstance(store, dict) else {}
                stored_version = stored_entry.get('version') if isinstance(stored_entry, dict) else stored_entry
                stored_updated = stored_entry.get('updated') if isinstance(stored_entry, dict) else None
                stored_updated_epoch = stored_entry.get('updated_epoch') if isinstance(stored_entry, dict) else None

                if stored_version is None:
                    print(f"[{self._timestamp()}] First Android run detected for {package_name}. Storing version {current_version}")
                    extra = {'updated': normalized_updated} if normalized_updated else None
                    if updated_epoch is not None:
                        extra = (extra or {})
                        extra['updated_epoch'] = updated_epoch
                    self.store_version('android', package_name, current_version, extra=extra)
                elif normalized_updated or updated_epoch is not None:
                    if stored_updated is None and stored_updated_epoch is None:
                        print(
                            f"[{self._timestamp()}] Android updated date tracked for {package_name} the first time: {normalized_updated}."
                        )
                        extra = {'updated': normalized_updated} if normalized_updated else {}
                        if updated_epoch is not None:
                            extra['updated_epoch'] = updated_epoch
                        self.store_version('android', package_name, current_version, extra=extra)
                    else:
                        updated_changed = False
                        trend_date = None
                        if updated_epoch is not None and stored_updated_epoch is not None:
                            if updated_epoch != stored_updated_epoch:
                                updated_changed = True
                                trend_date = 1 if updated_epoch > stored_updated_epoch else -1
                        elif normalized_updated and normalized_updated != stored_updated:
                            updated_changed = True
                            trend_date = self._compare_date_order(normalized_updated, stored_updated)

                        if updated_changed:
                            if trend_date == -1:
                                self.log_updated_regression(
                                    'android',
                                    package_name,
                                    stored_updated or str(stored_updated_epoch),
                                    normalized_updated or str(updated_epoch),
                                )
                            else:
                                print(
                                    f"[{self._timestamp()}] Android updated date change detected: "
                                    f"{stored_updated or stored_updated_epoch} ??' {normalized_updated or updated_epoch}"
                                )
                                play_link = f"https://play.google.com/store/apps/details?id={package_name}"
                                if self.send_email_alert(
                                    stored_updated or str(stored_updated_epoch),
                                    normalized_updated or str(updated_epoch),
                                    title=f"Android: {package_name}",
                                    link=play_link,
                                    subject_platform="Android",
                                ):
                                    extra = {'updated': normalized_updated} if normalized_updated else {}
                                    if updated_epoch is not None:
                                        extra['updated_epoch'] = updated_epoch
                                    self.store_version('android', package_name, current_version, extra=extra)
                                    self.log_version_change(
                                        'android',
                                        package_name,
                                        stored_updated or str(stored_updated_epoch),
                                        normalized_updated or str(updated_epoch),
                                        extra={'version': current_version, 'event': 'android_updated_change'},
                                    )
                                else:
                                    any_success = False
                else:
                    trend = self._compare_version_order(current_version, stored_version)
                    if trend == -1:
                        self.log_version_regression('android', package_name, stored_version, current_version)
                    elif trend == 1 and current_version != stored_version:
                        print(f"[{self._timestamp()}] Android version change detected for {package_name}: {stored_version} → {current_version}")
                        play_link = f"https://play.google.com/store/apps/details?id={package_name}"
                        if self.send_email_alert(
                            stored_version,
                            current_version,
                            title=f"Android: {package_name}",
                            link=play_link,
                            subject_platform="Android",
                        ):
                            self.store_version('android', package_name, current_version)
                            self.log_version_change('android', package_name, stored_version, current_version)
                        else:
                            any_success = False

        # Check iOS identifiers if configured
        if self.ios_ids:
            for ios_id in self.ios_ids:
                info = self.fetch_ios_version(ios_id)
                if not info:
                    print(f"[{self._timestamp()}] Failed to fetch iOS info for {ios_id}. Skipping.")
                    any_success = False
                    continue
                current_version = info.get('version')
                app_name = info.get('trackName', ios_id)
                stored_version = self.get_stored_version('ios', ios_id)
                if stored_version is None:
                    print(f"[{self._timestamp()}] First iOS run detected for {ios_id}. Storing version {current_version}")
                    self.store_version('ios', ios_id, current_version, extra={'trackViewUrl': info.get('trackViewUrl'), 'trackName': app_name})
                elif current_version != stored_version:
                    trend = self._compare_version_order(current_version, stored_version)
                    if trend == -1:
                        self.log_version_regression('ios', ios_id, stored_version, current_version)
                    else:
                        print(f"[{self._timestamp()}] iOS version change detected for {ios_id}: {stored_version} → {current_version}")
                        link = info.get('trackViewUrl')
                        if self.send_email_alert(
                            stored_version,
                            current_version,
                            title=f"iOS: {app_name}",
                            link=link,
                            subject_platform="iOS",
                        ):
                            self.store_version('ios', ios_id, current_version, extra={'trackViewUrl': link, 'trackName': app_name})
                            self.log_version_change('ios', ios_id, stored_version, current_version)
                        else:
                            any_success = False
        else:
            print(f"[{self._timestamp()}] No IOS_BUNDLE_ID configured; skipping iOS checks")

        if any_success:
            print(f"[{self._timestamp()}] Version check cycle completed successfully")
        else:
            print(f"[{self._timestamp()}] Version check cycle completed with errors")
        return any_success
    
    @staticmethod
    def _timestamp() -> str:
        """Return current timestamp in readable format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    """Main entry point."""
    try:
        monitor = VersionMonitor()
        success = monitor.run_check()
        sys.exit(0 if success else 1)
    except ValueError as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
