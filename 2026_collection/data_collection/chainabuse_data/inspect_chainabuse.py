import json
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.chainabuse.com/category/other-blackmail?page=1"

options = webdriver.ChromeOptions()

# Keep the browser visible during debugging.
driver = webdriver.Chrome(options=options)

try:
    driver.get(URL)

    input("Once the page has loaded, press Enter...")

    print("\nCurrent URL:")
    print(driver.current_url)

    print("\nPage Title:")
    print(driver.title)

    print("\nReport Cards:")
    cards = driver.find_elements(
        By.CSS_SELECTOR,
        "div[class*='ScamReportCard']"
    )

    print(f"Found {len(cards)} possible report cards.")

    for index, card in enumerate(cards[:3], start=1):
        print(f"\n--- REPORT {index} ---")
        print(card.text[:1000])

        links = card.find_elements(By.TAG_NAME, "a")

        for link in links:
            print("Link:", link.get_attribute("href"))

    print("\nPagination Links:")

    links = driver.find_elements(
        By.CSS_SELECTOR,
        "a[href*='page=']"
    )

    for link in links[:20]:
        print(link.get_attribute("href"))

    # Save rendered HTML for inspection.
    output = Path("chainabuse_page.html")
    output.write_text(
        driver.page_source,
        encoding="utf-8"
    )

    print(f"\nSaved HTML to {output}")

finally:
    driver.quit()