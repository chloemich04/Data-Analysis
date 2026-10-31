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

RAW_CSV = "chainabuse_raw_reports.csv"

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


def load_existing_report_ids():
    """
    Load report IDs already saved in the raw CSV.
    """

    existing_ids = set()

    if not os.path.exists(RAW_CSV):
        return existing_ids

    with open(RAW_CSV, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            report_id = row.get("report_id")

            if report_id:
                existing_ids.add(report_id)

    return existing_ids


def save_report(report_data):
    """
    Append one report to the raw dataset.
    """

    file_exists = os.path.exists(RAW_CSV)

    with open(RAW_CSV, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=CSV_FIELDS
        )

        if not file_exists or os.path.getsize(RAW_CSV) == 0:
            writer.writeheader()

        writer.writerow(report_data)


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

    existing_ids = load_existing_report_ids()

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
                if target_reports is not None and total_new_reports >= target_reports:
                    print(f"\nTarget reached: {total_new_reports} new reports.")
                    return

                print(f"Saved report: {report_id}")
                print(f"Message length: {report_data['message_length']}")

                # Respectful delay between requests
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                print(f"Error processing report {index + 1}: {e}")
                time.sleep(random.uniform(2, 4))
                continue

        print(f"\nFinished page {page_number + 1}.")

    print("\n" + "=" * 65)
    print("COLLECTION COMPLETE")
    print("=" * 65)

    print(f"New reports collected: {total_new_reports}")
    print(f"Total unique reports saved: {len(existing_ids)}")


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


if __name__ == "__main__":
    main()