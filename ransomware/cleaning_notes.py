import pandas as pd
import re

df = pd.read_csv("ransom_notes_with_content.csv")

# Remove null content
df = df.dropna(subset=["content"])

# Remove rows that still contain any HTML tags
html_pattern = r"<[^>]+>"
df = df[~df["content"].str.contains(html_pattern, na=False)]

# Reset index
df = df.reset_index(drop=True)

df.to_csv("ransomware_notes_clean.csv", index=False)
print("Cleaning complete. Final dataset size:", len(df))
