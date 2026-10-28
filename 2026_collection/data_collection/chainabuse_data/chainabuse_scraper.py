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
from selenium.webdriver.support import expected_conditions as EC

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

        #inspect_full_report(driver)

        reports = test_multiple_reports(driver, num_reports=10)
        import csv

        with open(
            "chainabuse_full_reports_test.csv",
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "report_id",
                    "report_url",
                    "message",
                    "message_length"
                ]
            )

            writer.writeheader()
            writer.writerows(reports)

        print("Saved test results to chainabuse_full_reports_test.csv")
        return

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
