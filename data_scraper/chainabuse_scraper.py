import csv
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

def extract_sender_and_time(line):
    # Case 1: "Anonymous 5 hours ago"
    match_relative = re.match(r"^(.*)\s+(\d+\s+\w+\s+ago)$", line)
    if match_relative:
        return match_relative.group(1).strip(), match_relative.group(2).strip()

    # Case 2: "Anonymous on Oct 3, 2025"
    match_absolute = re.match(r"^(.*)\s+on\s+(.*\d{4})$", line)
    if match_absolute:
        return match_absolute.group(1).strip(), match_absolute.group(2).strip()

    # Case 3: No match
    return "", ""


options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

start_URL = "https://chainabuse.com/category/other-blackmail?page=6"
driver.get(start_URL)
time.sleep(5)

cards_message = driver.find_elements(By.CSS_SELECTOR, "div[class*='create-ScamReportCard__body']")
cards_do_add = driver.find_elements(By.CSS_SELECTOR, "div[class*='create-ReportedSection variant-default']")

with open("chainabuse_reports.csv", "a", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    #writer.writerow(["Message", "Submitted By", "Time", "Reported Addresses/Domains"])

    for i in range(len(cards_message)):
        block = cards_message[i].text.strip().split("\n")
        message = ""
        submitted_by = ""
        time_reported = ""

        for line in block:
            if "Anonymous" in line:
                submitted_by, time_reported = extract_sender_and_time(line)
            else:
                # Remove leading UTC timestamp if present
                cleaned_line = re.sub(r"^\d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2}UTC:\s*", "", line)
                message += cleaned_line + " "

        address_block = cards_do_add[i].text.strip().replace("\n", ", ")
        writer.writerow([message.strip(), submitted_by, time_reported, address_block])

driver.quit()
