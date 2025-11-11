"""
scamwave_scraper.py
Full research scraper for scamwave.com/scammers/
- Uses Playwright to render JS & wait for table rows
- Visits each profile page (if link present) and extracts:
    - name, status, profile_url
    - visible emails, phones, crypto-like addresses
    - full profile text (sanitized)
- Saves output to JSON and CSV
- Polite: rate-limits, user-agent, error handling
USAGE: python scamwave_scraper.py
"""

import re
import time
import json
import csv
import os
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
from bs4 import BeautifulSoup

# ---------- Config ----------
START_URL = "https://scamwave.com/scammers/"
OUTPUT_JSON = "scamwave_profiles.json"
OUTPUT_CSV = "scamwave_profiles.csv"
USER_AGENT = "ResearchScraper/1.0 (chloemichelle04@gmail.com)"
# polite delay between profile page visits (seconds)
DELAY_BETWEEN = 1.5
# max profiles to scrape (set low for testing)
MAX_PROFILES = 200

# Regex for contact indicators
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', re.I)
PHONE_RE = re.compile(r'(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}')
# crude crypto pattern (BTC/ETH-like addresses) — will need refinement for production
CRYPTO_RE = re.compile(r'\b(0x[a-fA-F0-9]{30,64}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b')

# ---------- Helpers ----------
def extract_contact_indicators(text: str) -> Dict[str, List[str]]:
    emails = sorted(set(EMAIL_RE.findall(text)))
    phones = sorted(set(PHONE_RE.findall(text)))
    cryptos = sorted(set(CRYPTO_RE.findall(text)))
    # Normalization: strip spaces in phones, basic cleanup
    phones_clean = []
    for p in phones:
        p_clean = re.sub(r'[\s\-()]+', '', p)
        # filter out short false positives
        if len(re.sub(r'\D', '', p_clean)) >= 7:
            phones_clean.append(p_clean)
    return {"emails": emails, "phones": phones_clean, "crypto_addrs": cryptos}

def safe_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # remove script/style to avoid noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # collapse multiple blanks
    text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
    return text

# ---------- Scraper ----------
def run_scraper(max_profiles: int = MAX_PROFILES):
    profiles = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            print("→ Navigating to list page:", START_URL)
            page.goto(START_URL, timeout=30000)
            # Wait for the table body to be populated
            print("→ Waiting for table rows to appear...")
            # Wait for at least one row to be inserted into tbody#myTable
            page.wait_for_selector("tbody#myTable tr", timeout=20000)
            # give a short extra buffer for slow pages
            time.sleep(1.0)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            tbody = soup.select_one("tbody#myTable")
            if not tbody:
                print("⚠️ No tbody#myTable found after rendering. Exiting.")
                return []
            rows = tbody.find_all("tr")
            print(f"→ Found {len(rows)} table rows (may include header rows).")
            # iterate rows and extract basic fields & links
            count = 0
            for idx, row in enumerate(rows):
                if count >= max_profiles:
                    break
                cols = row.find_all(["td", "th"])
                if not cols:
                    continue
                # attempt to find name and status in first two columns
                name = cols[0].get_text(strip=True) if len(cols) > 0 else None
                status = cols[1].get_text(strip=True) if len(cols) > 1 else None
                # find link in first column if present
                a = cols[0].find("a")
                profile_rel = a.get("href") if a and a.has_attr("href") else None
                profile_url = None
                if profile_rel:
                    # make absolute
                    profile_url = page.url.rstrip("/") + "/" + profile_rel.lstrip("/")
                    # normalize (remove double slashes)
                    profile_url = re.sub(r'(?<!:)//+', '/', profile_url)
                profile = {
                    "name": name,
                    "status": status,
                    "profile_url": profile_url,
                    "details_text": None,
                    "emails": [],
                    "phones": [],
                    "crypto_addrs": []
                }
                # If there is a profile page, visit it and extract details
                if profile_url:
                    try:
                        print(f"  → Visiting profile ({count+1}): {profile_url}")
                        # open new tab to avoid losing list state
                        prof_page = context.new_page()
                        prof_page.goto(profile_url, timeout=30000)
                        # Wait for network idle or table content to load
                        prof_page.wait_for_load_state("networkidle", timeout=15000)
                        prof_html = prof_page.content()
                        prof_text = safe_text_from_html(prof_html)
                        indicators = extract_contact_indicators(prof_text)
                        profile["details_text"] = prof_text[:20000]  # truncate to sane size
                        profile["emails"] = indicators["emails"]
                        profile["phones"] = indicators["phones"]
                        profile["crypto_addrs"] = indicators["crypto_addrs"]
                        prof_page.close()
                        time.sleep(DELAY_BETWEEN)
                    except PWTimeoutError:
                        print("    ⚠️ Timeout when visiting profile:", profile_url)
                    except Exception as e:
                        print("    ⚠️ Error scraping profile:", e)
                else:
                    # no profile URL — attempt to parse any inline contact info in the row itself
                    row_html = str(row)
                    row_text = safe_text_from_html(row_html)
                    indicators = extract_contact_indicators(row_text)
                    profile["emails"] = indicators["emails"]
                    profile["phones"] = indicators["phones"]
                    profile["crypto_addrs"] = indicators["crypto_addrs"]

                profiles.append(profile)
                count += 1

            print(f"→ Scraped {len(profiles)} profiles (limited by max_profiles={max_profiles}).")
        finally:
            browser.close()

    # ---------- Save outputs ----------
    print("→ Saving JSON to", OUTPUT_JSON)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    # Save CSV (flattening details)
    print("→ Saving CSV to", OUTPUT_CSV)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "status", "profile_url", "emails", "phones", "crypto_addrs", "details_snippet"
        ])
        writer.writeheader()
        for p in profiles:
            writer.writerow({
                "name": p.get("name"),
                "status": p.get("status"),
                "profile_url": p.get("profile_url"),
                "emails": ";".join(p.get("emails", [])),
                "phones": ";".join(p.get("phones", [])),
                "crypto_addrs": ";".join(p.get("crypto_addrs", [])),
                "details_snippet": (p.get("details_text") or "")[:300].replace("\n", " ")
            })
    print("→ Done. Files saved. Be sure to examine & sanitize data before publishing.")
    return profiles

if __name__ == "__main__":
    # ensure working dir info
    print("Working dir:", os.getcwd())
    run_scraper(max_profiles=MAX_PROFILES)