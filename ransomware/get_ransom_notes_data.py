# used https://www.ransomware.live/ransomnotes to get data
import pandas as pd
import requests
from bs4 import BeautifulSoup

df = pd.read_csv("ransomware.csv")

results = []

for _, row in df.iterrows():
    url = row["file_link"]
    note_text = None

    try:
        print(f"[+] Fetching {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Try to extract ONLY the ransom note section
        code_block = soup.find("code", {"id": "Content"})

        if code_block:
            note_text = code_block.get_text("\n").strip()
        else:
            # Fallback if no formatted code block exists
            note_text = soup.get_text("\n").strip()

    except Exception as e:
        print(f"[-] Failed to fetch {url}: {e}")

    results.append({
        "ransom_group": row["ransom_group"],
        "file_name": row["file_name"],
        "file_link": url,
        "content": note_text
    })

output_df = pd.DataFrame(results)
output_df.to_csv("ransom_notes_with_content.csv", index=False)
print("[✔] Done! Saved to ransom_notes_with_content.csv")
