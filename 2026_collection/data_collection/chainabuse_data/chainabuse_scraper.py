"""Clean Chainabuse category-page collector (one page per run).

Based on the original Selenium scraper, with card-scoped extraction.
Collects publicly visible report *previews*, not necessarily full narratives.
"""

import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

CATEGORY = "other-blackmail" # determines which Chainabuse category is being collected
PAGE = 0 # determines which page will be examined
HEADLESS = False  # Keep the browser visible while we verify pagination.
OUTPUT = Path("chainabuse_clean_reports.csv") # determines where the colledcted data will be saved

BASE_URL = f"https://chainabuse.com/category/{CATEGORY}"
FIELDS = [
    "category", "requested_page", "selected_page", "source_url",
    "collected_at_utc", "card_position", "message_preview",
    "submitted_by", "time_reported", "reported_addresses_domains",
]


def parse_submission(text):
    """Split 'Submitted by Anonymous on Oct 15, 2026' when possible."""
    cleaned = re.sub(r"^Submitted by\s+", "", text.strip(), flags=re.I)
    match = re.match(r"^(.*?)\s+on\s+(.+)$", cleaned)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    match = re.match(r"^(.*?)\s+(\d+\s+\w+\s+ago)$", cleaned)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return cleaned, ""


def first_text(parent, selector):
    matches = parent.find_elements(By.CSS_SELECTOR, selector)
    return matches[0].text.strip() if matches else ""


def extract_cards(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, ".create-ScamReportCard")
    rows = []
    selected = driver.find_elements(
        By.CSS_SELECTOR, ".create-ResultsSection__pagination button[aria-current='true']"
    )
    selected_page = selected[0].text.strip() if selected else "unknown"

    for position, card in enumerate(cards, start=1):
        preview = first_text(card, ".create-ScamReportCard__preview-description")
        submission = first_text(card, ".create-ScamReportCard__submitted-info")
        author, reported_time = parse_submission(submission)
        addresses = [
            el.text.strip()
            for el in card.find_elements(
                By.CSS_SELECTOR,
                ".create-ReportedSection__address-section .create-ResponsiveAddress__text",
            )
            if el.text.strip()
        ]
        rows.append({
            "category": CATEGORY,
            "requested_page": PAGE,
            "selected_page": selected_page,
            "source_url": driver.current_url,
            "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "card_position": position,
            "message_preview": preview,
            "submitted_by": author,
            "time_reported": reported_time,
            "reported_addresses_domains": json.dumps(addresses, ensure_ascii=False),
        })
    return rows, selected_page


def main():
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    # Modern Selenium manages ChromeDriver automatically.
    driver = webdriver.Chrome(options=options)
    try:
        url = f"{BASE_URL}?page={PAGE}"
        print(f"Opening {url}")
        driver.get(url)
        WebDriverWait(driver, 25).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, ".create-ScamReportCard")) > 0
        )
        # Give client-side pagination a brief chance to settle.
        time.sleep(2)
        rows, selected_page = extract_cards(driver)
        print(f"Requested page: {PAGE}; UI selected page: {selected_page}")
        print(f"Report cards found: {len(rows)}")

        # Chainabuse uses zero-based URL pagination.
        # The displayed page number starts at 1.
        expected_ui_page = PAGE + 1

        # Convert the selected page number to an integer
        selected_page = int(selected_page)


        if selected_page != expected_ui_page:
            print(
                f"WARNING: Expected UI page {expected_ui_page}, "
                f"but found page {selected_page}. "
                "Not saving."
            )
            return

        print("Pagination verified successfully!")
        if not rows:
            print("No report cards found; no CSV written.")
            return

        # Overwrite on each run to keep this first test reproducible.
        with OUTPUT.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(rows)} rows to {OUTPUT.resolve()}")
        print("First preview:", rows[0]["message_preview"][:200])
    except TimeoutException:
        print("Timed out waiting for report cards. Check page load, login, or site changes.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
