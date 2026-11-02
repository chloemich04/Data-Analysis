"""Clean Chainabuse category-page collector (one page per run).

Based on the original Selenium scraper, with card-scoped extraction.
Collects publicly visible report *previews*, not necessarily full narratives.
"""

import csv
import os
import json
import re
import time
import random
import traceback
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException
)

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

CSV_FIELDS = [
    "report_id",
    "report_url",
    "category",
    "page_number",
    "card_position",
    "message_preview",
    "full_message",
    "message_length",
    "collected_at_utc"
]

DATASET_DIR = Path("datasets")
RAW_DIR = DATASET_DIR / "raw"
LOG_DIR = DATASET_DIR / "logs"

FAILURE_CSV = LOG_DIR / "chainabuse_failures.csv"

FAILURE_FIELDS = [
    "category", "page_number", "card_position", "source_url",
    "error_type", "error_message", "failed_at_utc"
]

def setup_directories():
    """Ensure that the necessary directories exist."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_raw_csv(category):
    """Return the path to the raw CSV file for a given category."""
    return RAW_DIR / f"chainabuse_{category.replace('-', '_')}.csv"

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


def handle_cookie_banner(driver):
    """
    Handles the cookie consent banner if it appears.
    """

    print("\nChecking for cookie banner...")

    try:
        cookie_banner = WebDriverWait(driver,5).until(
            EC.visibility_of_element_located((
                By.CSS_SELECTOR,
                '[aria-label="CookieConsent Banner"]'
            ))
        )

        print("Cookie banner detected.")

        # Find the available buttons
        buttons = cookie_banner.find_elements(
            By.TAG_NAME,
            "button"
        )

        print("Available cookie buttons:")

        for button in buttons:
            print(f"- {button.text}")

        # Prefer rejecting optional cookies
        for button in buttons:
            button_text = button.text.strip().lower()

            if any(word in button_text for word in [
                "reject",
                "decline",
                "deny"
            ]):
                button.click()

                print("Optional cookies rejected.")
                return
        print("No reject button found. Please handle the banner manually.")
    
    except TimeoutException:
        print("No visible cookie banner detected.")


def load_existing_report_ids(category):
    """
    Load report IDs already saved in the raw CSV.
    """

    existing_ids = set()
    output_file = get_raw_csv(category)

    if not output_file.exists():
        return existing_ids

    with output_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            report_id = row.get("report_id", "").strip()

            if report_id:
                existing_ids.add(report_id)

    return existing_ids


def save_report(report_data):
    """
    Append one report to the raw dataset.
    """

    category = report_data["category"]
    output_file = get_raw_csv(category)

    write_header = (
        not output_file.exists()
        or output_file.stat().st_size == 0
    )

    with output_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)

        if write_header:
            writer.writeheader()

        writer.writerow(report_data)


def log_failure(category, page_number, card_position, source_url, error):
    """
    Record a failed report extraction without stopping collection.
    """

    write_header = (
        not FAILURE_CSV.exists()
        or FAILURE_CSV.stat().st_size == 0
    )

    failure_data = {
        "category": category,
        "page_number": page_number,
        "card_position": card_position,
        "source_url": source_url,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "failed_at_utc": datetime.now(timezone.utc).isoformat()
    }

    with FAILURE_CSV.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FAILURE_FIELDS)

        if write_header:
            writer.writeheader()

        writer.writerow(failure_data)

    print(
        f"Failure logged: page {page_number + 1 if isinstance(page_number, int) else 'unknown'}, "
        f"report {card_position}"
    )


def extract_full_report(driver, page_number, card_position, preview, category):
    """
    Extract a full report from its details page.
    """

    report_url = driver.current_url

    report_id = report_url.split("/report/")[1].split("?")[0]

    description = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((
            By.CSS_SELECTOR,
            ".create-ScamReportDetails__description"
        ))
    )

    full_message = description.text.strip()

    report_data = {
        "report_id": report_id,
        "report_url": report_url,
        "category": category,
        "page_number": page_number,
        "card_position": card_position,
        "message_preview": preview,
        "full_message": full_message,
        "message_length": len(full_message),
        "collected_at_utc": datetime.now(timezone.utc).isoformat()
    }

    return report_data


def inspect_full_report(driver):
    """
    Opens the first report and extracts its full description.
    """

    print("\n--- Testing full report extraction ---")

    # Handle cookie banner before interacting with cards
    handle_cookie_banner(driver)

    cards = driver.find_elements(
        By.CSS_SELECTOR,
        ".create-ScamReportCard"
    )

    if not cards:
        print("No report cards found.")
        return

    print(f"Found {len(cards)} report cards.")

    original_url = driver.current_url

    print(f"Original URL: {original_url}")

    first_card = cards[0]

    clickable_area = first_card.find_element(
        By.CSS_SELECTOR,
        ".create-ScamReportCard__main"
    )

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        clickable_area
    )

    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            ".create-ScamReportCard__main"
        ))
    )

    clickable_area.click()

    # Wait until the report page opens
    WebDriverWait(driver, 15).until(
        lambda d: "/report/" in d.current_url
    )

    report_url = driver.current_url

    report_id = report_url.split("/report/")[1].split("?")[0]

    print(f"\nReport ID: {report_id}")
    print(f"Report URL: {report_url}")

    # Extract the full report message
    description_element = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((
            By.CSS_SELECTOR,
            ".create-ScamReportDetails__description"
        ))
    )

    report_message = description_element.text.strip()

    print("\n--- Extracted Report Message ---")
    print(report_message)

    # Save the extracted information
    report_data = {
        "report_id": report_id,
        "report_url": report_url,
        "message": report_message,
        "message_length": len(report_message)
    }

    print("\n--- Structured Report Data ---")
    print(report_data)

    return report_data


def scrape_multiple_pages(driver, start_page=0,
                          max_pages=3, category="other-blackmail", target_reports=None):
    """
    Scrape multiple Chainabuse category pages.

    Pages are zero-indexed:
    page=0 -> UI page 1
    page=1 -> UI page 2
    """

    setup_directories()

    existing_ids = load_existing_report_ids(category)

    total_failures = 0
    total_duplicates = 0

    print(f"\nPreviously collected reports: {len(existing_ids)}")

    total_new_reports = 0

    for page_number in range(start_page, start_page + max_pages):
        category_url = (
            f"https://chainabuse.com/category/{category}?page={page_number}"
        )

        print(f"\n{'=' * 65}")
        print(f"SCRAPING PAGE {page_number + 1}")
        print(f"{'=' * 65}")

        driver.get(category_url)

        try:
            handle_cookie_banner(driver)

            cards = WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    ".create-ScamReportCard"
                ))
            )
        except TimeoutException:
            print(f"No report cards found on page {page_number + 1}.")
            break

        # Wait for client-side pagination to display the requested page.
        WebDriverWait(driver, 15).until(
            lambda d: any(
                el.text.strip() == str(page_number + 1)
                for el in d.find_elements(
                    By.CSS_SELECTOR,
                    ".create-ResultsSection__pagination button[aria-current='true']"
                )
            )
        )
        total_cards = len(driver.find_elements(By.CSS_SELECTOR, ".create-ScamReportCard"))

        print(f"Found {total_cards} report cards.")

        target_reached = False

        for index in range(total_cards):

            print(f"\nProcessing report {index + 1}/{total_cards}")

            try:
                # Reload the listing page for each report
                if "/report/" in driver.current_url:
                    driver.get(category_url)

                WebDriverWait(driver, 15).until(
                    lambda d: any(
                        el.text.strip() == str(page_number + 1)
                        for el in d.find_elements(
                            By.CSS_SELECTOR,
                            ".create-ResultsSection__pagination button[aria-current='true']"
                        )
                    )
                )
                cards = driver.find_elements(By.CSS_SELECTOR, ".create-ScamReportCard")
                card = cards[index]

                preview_element = card.find_element(
                    By.CSS_SELECTOR,
                    ".create-ScamReportCard__preview-description"
                )

                preview = preview_element.text.strip()

                clickable_area = card.find_element(
                    By.CSS_SELECTOR,
                    ".create-ScamReportCard__main"
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    clickable_area
                )

                time.sleep(1)

                try:
                    clickable_area.click()
                except ElementClickInterceptedException:
                    print("Click intercepted. Checking cookie banner.")

                    handle_cookie_banner(driver)

                    clickable_area.click()

                WebDriverWait(driver, 15).until(
                    lambda d: "/report/" in d.current_url
                )

                report_id = (
                    driver.current_url.split("/report/")[1].split("?")[0]
                )

                if report_id in existing_ids:
                    total_duplicates += 1
                    print(f"Skipping duplicate: {report_id}")
                    time.sleep(random.uniform(2, 4))
                    continue

                report_data = extract_full_report(
                    driver,
                    page_number,
                    index + 1,
                    preview,
                    category
                )

                save_report(report_data)

                existing_ids.add(report_id)

                total_new_reports += 1

                target_reached = (
                    target_reports is not None
                    and total_new_reports >= target_reports
                )

                if target_reached:
                    print(f"\nTarget of {target_reports} new reports reached.")
                    break

                print(f"Saved report: {report_id}")
                print(f"Message length: {report_data['message_length']}")

                # Respectful delay between requests
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                total_failures += 1

                print(f"Error processing report {index + 1}: {e}")

                log_failure(
                    category=category,
                    page_number=page_number,
                    card_position=index + 1,
                    source_url=driver.current_url,
                    error=e
                )

                continue

        print(f"\nFinished page {page_number + 1}.")
        if target_reached:
            break

    print("\n" + "=" * 65)
    print("COLLECTION COMPLETE")
    print("=" * 65)

    print(f"Category: {category}")
    print(f"New reports collected: {total_new_reports}")
    print(f"Total unique reports saved: {len(existing_ids)}")
    print(f"Total duplicates skipped: {total_duplicates}")
    print(f"Total failures logged: {total_failures}")

    print(f"\nRaw data saved to: {get_raw_csv(category)}")
    print(f"Failure log saved to: {FAILURE_CSV}")
    print("=" * 65)

def test_multiple_reports(driver, num_reports=10):
    """
    Tests extraction of multiple reports from the current category page.
    """

    print("\n--- Testing Multiple Report Extraction ---")

    category_url = driver.current_url

    handle_cookie_banner(driver)

    # Find report cards on the category page
    cards = WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            ".create-ScamReportCard"
        ))
    )

    total_reports = len(cards)

    print(f"Found {total_reports} reports.")

    num_reports = min(num_reports, total_reports)

    collected_reports = []

    for index in range(num_reports):

        print(f"\n{'=' * 60}")
        print(f"Extracting report {index + 1} of {num_reports}")
        print(f"{'=' * 60}")

        try:
            # Return to category page
            driver.get(category_url)

            # Wait for report cards to load
            cards = WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    ".create-ScamReportCard"
                ))
            )

            # Select report by its position
            card = cards[index]

            clickable_area = card.find_element(
                By.CSS_SELECTOR,
                ".create-ScamReportCard__main"
            )

            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                clickable_area
            )

            time.sleep(1)

            clickable_area.click()

            # Wait for navigation to report details
            WebDriverWait(driver, 15).until(
                lambda d: "/report/" in d.current_url
            )

            report_url = driver.current_url

            report_id = report_url.split("/report/")[1].split("?")[0]

            # Wait for full report description
            description = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((
                    By.CSS_SELECTOR,
                    ".create-ScamReportDetails__description"
                ))
            )

            full_message = description.text.strip()

            report_data = {
                "report_id": report_id,
                "report_url": report_url,
                "message": full_message,
                "message_length": len(full_message)
            }

            collected_reports.append(report_data)

            print(f"Report ID: {report_id}")
            print(f"Message length: {len(full_message)} characters")

            print("\nFull message:")
            print(full_message)

            time.sleep(2)

        except Exception as e:
            print(f"Error extracting report {index + 1}: {e}")
            continue

    print("\n--- Extraction Test Complete ---")
    print(f"Successfully collected {len(collected_reports)} reports.")

    return collected_reports


def main_menu():
    while True:
        print("\n" + "=" * 55)
        print("CHAINABUSE DATA COLLECTOR".center(55))
        print("=" * 55)

        print("1. Start Data Collection\n2. View Collection Statistics\n3. View Available Categories\n" \
        "4. Exit")

        choice = input("\nSelect an option (1-4): ").strip()

        if choice == "1":
            print("\nStarting collection setup...")
            #configure_collection()
        elif choice == "2":
            print("\nDisplaying statistics...")
            # show_statistics
        elif choice == "3":
            print("\nDisplaying categories...")
            # show_categories
        elif choice == "4":
            print("\nExiting Chainabuse Data Collector.")
            break
        else:
            print("\nInvaild option. Please enter a number from 1 to 4.")

        
def get_positive_integer(prompt):
    """ Ask for a positive whole number """
    while True:
        value = input(prompt).strip()

        if value.isdigit() and int(value) > 0:
            return int(value)

        print("Please enter a positive whole number.")


def select_category():
    """ Select a verified Chainabuse category. """
    categories = {
        "1": ("Other Blackmail", "other-blackmail")
    }

    while True:
        print("\n========== SELECT CATEGORY ==========")
        print("1. Other Blackmail")
        print("0. Return to Main Menu")

        choice = input("Select category: ").strip()

        if choice == "0":
            return None

        if choice in categories:
            return categories[choice]

        print("Invalid category selection.")


def configure_collection():
    """Build collection settings from user input. """
    category = select_category()

    if category is None:
        return None

    category_name, category_slug = category

    print("\n========== COLLECTION METHOD ==========")
    print("1. Single Page\n2. Page Range\n3. Specific Number of New Reports\n0. Return to Main Menu")

    while True:
        choice = input("Select method: ").strip()

        if choice in ("0","1","2","3"):
            break

        print("Please select 0, 1, 2, or 3.")

    if choice == "0":
        return None

    start_page = get_positive_integer("Starting page (1 = first page): ")

    if choice == "1":
        settings = {
            "category": category_slug,
            "start_page": start_page - 1,
            "max_pages": 1,
            "target_reports": None
        }
    elif choice == "2":
        while True:
            end_page = get_positive_integer("Ending page: ")

            if end_page >= start_page:
                break

            print("Ending page must be at least the starting page.")

        settings = {
            "category": category_slug,
            "start_page": start_page - 1,
            "max_pages": end_page - start_page + 1,
            "target_reports": None
        }
    else:
        target = get_positive_integer(
            "How many NEW reports should be collected?"
        )

        max_pages = get_positive_integer(
            "Maximum pages to search (safety limit): "
        )

        settings = {
            "category": category_slug,
            "start_page": start_page - 1,
            "max_pages": max_pages,
            "target_reports": target
        }

    print("\n========== CONFIRM COLLECTION ==========")
    print(f"Category: {category_name}")
    print(f"Starting page: {start_page}")
    print(f"Maximum pages: {settings['max_pages']}")

    if settings["target_reports"] is not None:
        print(f"Target new reports: {settings['target_reports']}")

    confirmation = input("Start collection? [Y/N]: ").strip().lower()

    return settings if confirmation == "y" else None


def run_collection(settings):
    options = webdriver.ChromeOptions()

    if HEADLESS:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)

    try:
        scrape_multiple_pages(
            driver,
            start_page=settings["start_page"],
            max_pages=settings["max_pages"],
            category=settings["category"],
            target_reports=settings["target_reports"]
        )
    finally:
        driver.quit()


def main():
    while True:
        print("\n" + "=" * 55)
        print("CHAINABUSE DATA COLLECTOR".center(55))
        print("=" * 55)

        print("1. Start Data Collection\n2. View Available Categories\n3. Exit")

        choice = input("\nSelect an option (1-3): ").strip()

        if choice == "1":
            settings = configure_collection()

            if settings is not None:
                try:
                    run_collection(settings)
                except KeyboardInterrupt:
                    print("\nCollection interrupted by user")
                except Exception as error:
                    print(f"\nCollection error: {error}")
        elif choice == "2":
            print("\nCurrently supported categories: ")
            print("1. Other Blackmail")
            print("\nAdditional categories will be added after verification.")
        elif choice == "3":
            print("\nExiting Chainabuse Data Collector.")
            break
        else:
            print("\nInvaild selection. Please try again.")



# Bulk collector extension. Standard library + the original Selenium dependency.
import argparse
import concurrent.futures
import hashlib
import threading
from urllib.parse import urlsplit, urljoin


class SafeStop(RuntimeError):
    pass


def listing_text_key(text):
    """Compare rendered previews without layout-only whitespace differences."""
    import unicodedata
    return ' '.join(unicodedata.normalize('NFC', text).split())


def click_visible_card(driver, position):
    """Native pointer click at a hit-tested viewport point, even for tall cards.

    Never force a JavaScript click through an overlay. Reacquire the card on
    every poll because pagination/hydration can replace its DOM element.
    """
    from selenium.webdriver.common.actions.action_builder import ActionBuilder

    def point_ready(d):
        cards = d.find_elements(By.CSS_SELECTOR, '.create-ScamReportCard')
        if len(cards) < position:
            return False
        element = cards[position - 1].find_element(
            By.CSS_SELECTOR, '.create-ScamReportCard__main')
        return d.execute_script('''
          const e=arguments[0];
          e.scrollIntoView({block:'start',inline:'nearest',behavior:'instant'});
          const r=e.getBoundingClientRect();
          const left=Math.max(0,r.left), right=Math.min(innerWidth,r.right);
          const top=Math.max(0,r.top), bottom=Math.min(innerHeight,r.bottom);
          if(right-left<4 || bottom-top<4) return null;
          for(const fy of [0.25,0.5,0.75]) {
            for(const fx of [0.5,0.25,0.75]) {
              const x=Math.floor(left+(right-left)*fx);
              const y=Math.floor(top+(bottom-top)*fy);
              const hit=document.elementFromPoint(x,y);
              if(hit && (hit===e || e.contains(hit)) &&
                 !hit.closest('button,a,input,textarea,select')) return {x,y};
            }
          }
          return null;
        ''', element) or False

    for attempt in range(2):
        try:
            point = WebDriverWait(driver, 10).until(point_ready)
            actions = ActionBuilder(driver)
            actions.pointer_action.move_to_location(point['x'], point['y'])
            actions.pointer_action.click()
            actions.perform()
            return
        except (TimeoutException, ElementClickInterceptedException):
            if attempt:
                raise SafeStop('No unobstructed report-card click point; page retained for retry')
            handle_cookie_banner(driver)


def canonical_report(url):
    parsed = urlsplit(urljoin('https://chainabuse.com', url))
    if parsed.hostname not in ('chainabuse.com', 'www.chainabuse.com'):
        return None
    match = re.fullmatch(r'/report/([^/]+)/?', parsed.path)
    return ('https://chainabuse.com/report/' + match[1]) if match else None


class BulkCollector:
    """One listing browser and at most four detail browsers; no bypass behavior.

    Checkpoints advance only after every report on a page is durable. Failures
    leave that page resumable. CSV IDs are authoritative after a crash. Dedupe
    is per category, so a report belonging to two categories stays in both CSVs.
    Pagination is a moving view: rescan from page zero periodically to catch
    reports inserted before an existing checkpoint.
    """
    def __init__(self, args, listing=None):
        self.args = args
        self.listing = listing
        self.owns_listing = listing is None
        self.drivers = []
        self.local = threading.local()
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.stop = threading.Event()
        self.started = time.monotonic()
        self.stats = dict(saved=0, duplicates=0, failures=0, pages=0,
                          navigations=0, fallback_clicks=0)
        self.reason = 'limits reached'
        self.active_ids = set()
        self.retried_pending = set()
        self.state_path = Path(args.checkpoint)
        self.state = (json.loads(self.state_path.read_text(encoding='utf-8'))
                      if self.state_path.exists() else {'version': 1, 'categories': {}})
        if self.state.get('version') != 1:
            raise ValueError('Unsupported checkpoint version')

    def check(self):
        if self.stop.is_set():
            raise SafeStop('stop requested')
        if time.monotonic() - self.started >= self.args.max_seconds:
            raise SafeStop('time limit reached')

    def pace(self):
        # Shared start-to-start navigation pacing, including Selenium fallback.
        with self.lock:
            self.check()
            delay = max(0, self.next_request - time.monotonic())
            if self.stop.wait(delay):
                raise SafeStop('stop requested')
            self.check()
            self.next_request = time.monotonic() + self.args.interval
            self.stats['navigations'] += 1

    def browser(self):
        options = webdriver.ChromeOptions()
        options.page_load_strategy = 'eager'
        if self.args.headless:
            options.add_argument('--headless=new')
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        with self.lock:
            self.drivers.append(driver)
        return driver

    def guard(self, driver):
        text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        if any(s in text for s in ('verify you are human', 'access denied',
                                   'too many requests', 'checking your browser',
                                   'unusual traffic')) or driver.find_elements(
                                       By.CSS_SELECTOR, 'iframe[src*="captcha"]'):
            self.stop.set()
            raise SafeStop('access challenge or rate limit; stopping without bypass')
        phrases = ('sign in to continue', 'log in to continue',
                   'login to continue', 'sign up to continue')
        if any(phrase in text for phrase in phrases):
            if not self.args.login:
                raise SafeStop('Sign-in required; restart with --login')
            original_url = driver.current_url
            waiting = time.monotonic()
            print('\nSign-in is required again. Sign in in the existing Chrome window.')
            input('After signing in, press Enter here to continue (Ctrl+C cancels): ')
            self.started += time.monotonic() - waiting
            self.pace()
            driver.get(original_url)
            refreshed = driver.find_element(By.TAG_NAME, 'body').text.lower()
            if any(phrase in refreshed for phrase in phrases):
                raise SafeStop('Sign-in prompt still present after manual login')
            # Check access challenges too, without repeating the login prompt.
            self.guard(driver)

    def login(self):
        # Credentials stay in the browser. No cookie export or password storage.
        self.pace()
        self.listing.get('https://chainabuse.com/reports')
        print('\nSign in to Chainabuse in the Chrome window opened by this script.')
        print('Finish sign-in, return to the reports page, then return here.')
        input('Press Enter ONLY after you have signed in (Ctrl+C cancels): ')
        self.guard(self.listing)
        # Collection/benchmark time limits exclude time spent signing in.
        self.started = time.monotonic()

    def navigate(self, driver, url):
        self.pace()
        driver.get(url)
        self.guard(driver)

    def categories(self):
        self.navigate(self.listing, 'https://chainabuse.com/reports')
        WebDriverWait(self.listing, 20).until(lambda d: d.find_elements(
            By.CSS_SELECTOR, 'a[href*="/category/"]'))
        found = {}
        for link in self.listing.find_elements(By.CSS_SELECTOR, 'a[href*="/category/"]'):
            parsed = urlsplit(link.get_attribute('href') or '')
            match = re.fullmatch(r'/category/([a-z0-9-]+)/?', parsed.path)
            if parsed.hostname in ('chainabuse.com', 'www.chainabuse.com') and match:
                found[match[1]] = link.text.strip() or match[1]
        if not found:
            raise SafeStop('No category links found; verify site markup before collecting')
        return found

    def listing_page(self, category, page):
        url = f'https://chainabuse.com/category/{category}?page={page}'
        self.navigate(self.listing, url)
        try:
            WebDriverWait(self.listing, 20).until(lambda d: d.find_elements(
                By.CSS_SELECTOR, '.create-ScamReportCard'))
        except TimeoutException:
            self.guard(self.listing)
            # A timeout is not proof of an empty category or the final page.
            raise SafeStop('No cards loaded; page retained for retry')
        WebDriverWait(self.listing, 15).until(lambda d: any(
            el.text.strip() == str(page + 1) for el in d.find_elements(
                By.CSS_SELECTOR,
                ".create-ResultsSection__pagination button[aria-current='true']")))
        # One browser round trip captures every card's preview and public href.
        records = self.listing.execute_script('''return Array.from(
          document.querySelectorAll('.create-ScamReportCard')).map((c,i)=>({
            position:i+1,
            preview:c.querySelector('.create-ScamReportCard__preview-description')?.innerText||'',
            href:Array.from(c.querySelectorAll('a[href]')).map(a=>a.href)
                 .find(h=>h.includes('/report/'))||null,
            identity:c.innerText}));''')
        # Cache only against this exact ordered listing content, never merely
        # page number or preview text. A changed listing invalidates the cache.
        signature = hashlib.sha256(json.dumps(
            [r['identity'] for r in records], ensure_ascii=False).encode()).hexdigest()
        cache_path = LOG_DIR / 'chainabuse_links' / category / f'{page}.json'
        cached = {}
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding='utf-8'))
                if payload.get('signature') == signature:
                    cached = payload.get('links', {})
            except (ValueError, OSError):
                pass
        identities = [listing_text_key(r['identity']) for r in records]
        for record in records:
            record['url'] = canonical_report(record['href']) if record['href'] else None
            # Identical cards cannot safely be identified by their position
            # across reloads, so do not reuse a cached URL for those cards.
            if not record['url'] and identities.count(identities[record['position'] - 1]) == 1:
                record['url'] = canonical_report(cached.get(str(record['position']), ''))
        for record in records:
            self.check()
            if self.stats['saved'] >= self.args.max_reports:
                raise SafeStop('new report limit reached; partial page retained')
            if record['url']:
                continue
            # Some versions expose clickable divs only. Preserve the listing in
            # its original tab; shift-click is not assumed to work on JS cards.
            self.pace()
            click_visible_card(self.listing, record['position'])
            WebDriverWait(self.listing, 15).until(lambda d: canonical_report(d.current_url))
            self.guard(self.listing)
            record['url'] = canonical_report(self.listing.current_url)
            self.stats['fallback_clicks'] += 1
            cached[str(record['position'])] = record['url']
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix('.tmp')
            with temporary.open('w', encoding='utf-8') as f:
                json.dump(dict(signature=signature, links=cached), f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, cache_path)
            # The full detail is already open: save now, without a worker
            # navigating to the same report a second time.
            report_id = record['url'].rsplit('/', 1)[-1]
            if report_id not in self.active_ids:
                try:
                    row = extract_full_report(self.listing, page, record['position'],
                                              record['preview'], category)
                    if canonical_report(self.listing.current_url) != record['url']:
                        raise SafeStop('Report redirected to a different URL')
                    self.commit_report(row)
                    record['_handled'] = True
                except SafeStop:
                    raise
                except Exception as error:
                    self.guard(self.listing)
                    self.queue_failure(category, page, record, error)
                    record['_handled'] = True
            if self.stats['saved'] >= self.args.max_reports:
                raise SafeStop('new report limit reached; partial page retained')
            self.navigate(self.listing, url)
            WebDriverWait(self.listing, 15).until(lambda d: any(
                e.text.strip() == str(page + 1) for e in d.find_elements(
                    By.CSS_SELECTOR,
                    ".create-ResultsSection__pagination button[aria-current='true']")))
            WebDriverWait(self.listing, 15).until(lambda d: len(d.find_elements(
                By.CSS_SELECTOR, '.create-ScamReportCard')) == len(records))
            expected = [listing_text_key(r['preview']) for r in records]
            def same_listing(driver):
                # Use the SAME DOM text API as the initial snapshot. Selenium
                # .text applies different hidden-text/whitespace rules from
                # innerText. Also allow the returned page time to hydrate.
                previews = driver.execute_script('''return Array.from(
                  document.querySelectorAll('.create-ScamReportCard')).map(c=>
                  c.querySelector('.create-ScamReportCard__preview-description')?.innerText||'');''')
                return [listing_text_key(p) for p in previews] == expected
            try:
                WebDriverWait(self.listing, 15).until(same_listing)
            except TimeoutException:
                raise SafeStop('Listing content/order changed during click fallback; page retained for retry')
        return records, url

    def commit_report(self, row):
        if not row['full_message']:
            raise ValueError('Empty full description; preview not substituted')
        save_report(row)
        with get_raw_csv(row['category']).open('a', encoding='utf-8') as f:
            f.flush()
            os.fsync(f.fileno())
        self.active_ids.add(row['report_id'])
        self.stats['saved'] += 1

    def queue_failure(self, category, page, record, error):
        """Persist unresolved reports before advancing past a failed card."""
        self.stats['failures'] += 1
        log_failure(category, page, record['position'], record['url'], error)
        pending = self.state['categories'].setdefault(category, {}).setdefault('pending_reports', {})
        report_id = record['url'].rsplit('/', 1)[-1]
        previous = pending.get(report_id, {})
        pending[report_id] = dict(url=record['url'], position=record['position'],
                                  preview=record['preview'], page=page,
                                  attempts=previous.get('attempts', 0) + 1,
                                  error_type=type(error).__name__, error=str(error),
                                  failed_at_utc=datetime.now(timezone.utc).isoformat())
        self.checkpoint()
        print(f'Queued report {report_id} for retry; continuing collection.')

    def retry_pending(self, pool, category):
        """One additional retry round/report/invocation; unresolved work stays durable.

        detail() already bounds navigation retries. Repeated empty narratives
        must not create a tight retry loop or blank successful CSV rows.
        """
        pending = self.state['categories'].setdefault(category, {}).setdefault('pending_reports', {})
        for report_id, record in list(pending.items()):
            if report_id in self.active_ids:
                del pending[report_id]
                self.checkpoint()
                continue
            key = (category, report_id)
            if key in self.retried_pending:
                continue
            self.check()
            if self.stats['saved'] >= self.args.max_reports:
                raise SafeStop('new report limit reached; unresolved reports retained in retry queue')
            self.retried_pending.add(key)
            try:
                # Main thread writes; signed-in mode still uses only its one
                # browser. There are no other outstanding futures here.
                row = pool.submit(self.detail, record, category, record['page']).result()
            except SafeStop:
                raise
            except Exception as error:
                self.queue_failure(category, record['page'], record, error)
                continue
            self.commit_report(row)
            del pending[report_id]
            self.checkpoint()
            print(f'Retry recovered report {report_id}.')

    def detail(self, record, category, page):
        # Login mode uses the exact browser that the user authenticated. One
        # worker prevents concurrent navigation of that shared browser.
        driver = self.listing if self.args.login else getattr(self.local, 'driver', None)
        if driver is None:
            driver = self.local.driver = self.browser()
        for attempt in range(self.args.retries + 1):
            try:
                self.navigate(driver, record['url'])
                row = extract_full_report(driver, page, record['position'],
                                          record['preview'], category)
                if canonical_report(driver.current_url) != record['url']:
                    raise SafeStop('Report redirected to a different URL')
                if not row['full_message']:
                    raise ValueError('Empty full description; preview not substituted')
                return row
            except SafeStop:
                raise
            except Exception:
                self.guard(driver)
                if attempt == self.args.retries:
                    raise
                if self.stop.wait(min(30, 2 ** (attempt + 1))):
                    raise SafeStop('stop requested')

    def checkpoint(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + '.tmp')
        with temporary.open('w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, self.state_path)

    def collect_category(self, pool, category):
        saved_ids = load_existing_report_ids(category)
        self.active_ids = saved_ids
        state = self.state['categories'].setdefault(category, {})
        self.retry_pending(pool, category)
        start = max(self.args.start_page, state.get('next_page', self.args.start_page))
        seen_pages = set()
        for page in range(start, start + self.args.max_pages):
            self.check()
            if self.stats['saved'] >= self.args.max_reports:
                raise SafeStop('new report limit reached')
            records, url = self.listing_page(category, page)
            fingerprint = hashlib.sha256('\n'.join(r['url'] for r in records).encode()).hexdigest()
            if not records or fingerprint in seen_pages or fingerprint == state.get('last_fingerprint'):
                raise SafeStop('empty or repeated listing; checkpoint retained')
            seen_pages.add(fingerprint)
            pending = []
            page_ids = set()
            for record in records:
                if record.get('_handled'):
                    continue
                report_id = record['url'].rsplit('/', 1)[-1]
                if report_id in saved_ids or report_id in page_ids:
                    self.stats['duplicates'] += 1
                else:
                    pending.append(record)
                    page_ids.add(report_id)
            # Only one bounded chunk is submitted at a time. Main thread alone
            # writes CSV/checkpoints and drains work before advancing the page.
            for offset in range(0, len(pending), self.args.workers):
                remaining = self.args.max_reports - self.stats['saved']
                if remaining <= 0:
                    raise SafeStop('new report limit reached')
                batch = pending[offset:offset + min(self.args.workers, remaining)]
                futures = {pool.submit(self.detail, r, category, page): r for r in batch}
                for future in concurrent.futures.as_completed(futures):
                    record = futures[future]
                    try:
                        row = future.result()
                    except SafeStop:
                        raise
                    except Exception as error:
                        self.queue_failure(category, page, record, error)
                        continue
                    self.commit_report(row)
                if offset + len(batch) < len(pending) and self.stats['saved'] >= self.args.max_reports:
                    raise SafeStop('new report limit reached; partial page retained')
            state.update(next_page=page + 1, last_fingerprint=fingerprint,
                         updated_at_utc=datetime.now(timezone.utc).isoformat())
            self.checkpoint()
            self.stats['pages'] += 1
            print(f'{category}: UI page {page + 1}, new reports this run: {self.stats["saved"]}')
            self.retry_pending(pool, category)

    def run(self):
        setup_directories()
        # Exclusive local lock prevents two processes racing on CSV/checkpoints.
        lock_path = RAW_DIR / '.collector.lock'
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, str(os.getpid()).encode())
        try:
            if self.listing is None:
                self.listing = self.browser()
            if self.args.login:
                self.login()
            if self.args.discover_categories or self.args.bulk:
                available = self.categories()
                if self.args.discover_categories:
                    print(json.dumps(available, indent=2))
                    return
                config = json.loads(Path(self.args.bulk).read_text(encoding='utf-8'))
                categories = config['categories']
                if not isinstance(categories, list) or not categories or not all(
                        isinstance(c, str) and c in available for c in categories):
                    raise ValueError('categories must be a nonempty list of exact live-discovered slugs')
            else:
                categories = [self.args.category]
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.workers) as pool:
                for category in dict.fromkeys(categories):
                    self.collect_category(pool, category)
        except KeyboardInterrupt:
            self.stop.set()
            self.reason = 'interrupted; current page will be replayed on resume'
        except Exception as error:
            self.reason = str(error) if isinstance(error, SafeStop) else f'{type(error).__name__}: {error}'
            if not isinstance(error, SafeStop):
                self.stats['failures'] += 1
                log_failure('', '', '', '', error)
        finally:
            self.stop.set()
            for driver in self.drivers:
                try:
                    driver.quit()
                except Exception:
                    pass
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)
            elapsed = time.monotonic() - self.started
            summary = dict(self.stats, elapsed_seconds=round(elapsed, 2),
                           pending_reports=sum(len(c.get('pending_reports', {}))
                                               for c in self.state['categories'].values()),
                           reports_per_minute=round(self.stats['saved'] * 60 / max(elapsed, .001), 2),
                           stop_reason=self.reason,
                           benchmark=self.args.benchmark)
            print(json.dumps(summary, indent=2))
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with (LOG_DIR / 'chainabuse_runs.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(summary) + '\n')
        return summary


def bulk_arguments(argv=None):
    parser = argparse.ArgumentParser(description='Resumable Chainabuse collector; no arguments opens original menu.')
    parser.add_argument('--bulk', help='JSON file: {"categories": [exact discovered slugs]}')
    parser.add_argument('--discover-categories', action='store_true')
    parser.add_argument('--category', default=CATEGORY)
    parser.add_argument('--start-page', type=int, default=0, help='Zero indexed')
    parser.add_argument('--max-pages', type=int, default=100, help='Per category, per invocation')
    parser.add_argument('--max-reports', type=int, default=1000, help='New rows globally this invocation')
    parser.add_argument('--max-seconds', type=float, default=3600)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--interval', type=float, default=2.0, help='Global minimum navigation interval, seconds (>=1)')
    parser.add_argument('--retries', type=int, choices=range(0, 4), default=1)
    parser.add_argument('--checkpoint', default='datasets/logs/chainabuse_checkpoint.json')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--login', action='store_true', help='Pause for manual sign-in; use the same visible browser for all collection')
    parser.add_argument('--benchmark', action='store_true', help='Real collection capped at 2 pages/category, 20 reports, 5 minutes')
    args = parser.parse_args(argv)
    if args.login and args.headless:
        parser.error('--login requires visible Chrome; omit --headless')
    if args.login:
        args.workers = 1
    if args.start_page < 0 or min(args.max_pages, args.max_reports, args.max_seconds) <= 0 or args.interval < 1:
        parser.error('Limits must be positive, start-page nonnegative, interval >= 1')
    if not all(__import__('math').isfinite(v) for v in (args.max_seconds, args.interval)):
        parser.error('Timing values must be finite')
    if args.benchmark:
        args.max_pages = min(args.max_pages, 2)
        args.max_reports = min(args.max_reports, 20)
        args.max_seconds = min(args.max_seconds, 300)
    return args


# Retain the original single-page, range, and target-count interactive setup.
# Its run_collection resolves this replacement at call time.
def scrape_multiple_pages(driver, start_page=0, max_pages=3,
                          category='other-blackmail', target_reports=None):
    args = bulk_arguments([])
    args.category = category
    args.start_page = start_page
    args.max_pages = max_pages
    args.max_reports = target_reports if target_reports is not None else 10 ** 12
    # Independent checkpoint per requested range avoids surprising menu skips.
    args.checkpoint = str(LOG_DIR / f'interactive_{category}_{start_page}_{max_pages}.json')
    return BulkCollector(args, listing=driver).run()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        main()
    else:
        BulkCollector(bulk_arguments()).run()
