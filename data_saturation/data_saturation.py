import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------
# Load your datasets
# ---------------------------
df_ransom = pd.read_csv("C:/Users/chloe/dev_projects/Data-Analysis/ransomware/ransomware_notes_clean.csv")
df_chain = pd.read_csv("C:/Users/chloe/dev_projects/Data-Analysis/data_scraper/chainabuse_reports_clean.csv")
df_reddit = pd.read_csv("C:/Users/chloe/dev_projects/Data-Analysis/reddit/reddit_dataset_clean.csv")

# Load keywords
keywords = []
with open("data_saturation_words.txt", "r", encoding="utf-8") as f:
    keywords = [w.strip().lower() for w in f.readlines() if w.strip()]


# ---------------------------
# Function to compute saturation curve
# ---------------------------
def compute_saturation(df, text_column, keywords):
    """
    Returns cumulative unique keyword hits across documents.
    """
    df[text_column] = df[text_column].fillna("").astype(str)

    seen_keywords = set()
    cumulative = []

    for text in df[text_column]:
        text_lower = text.lower()
        found = [kw for kw in keywords if kw in text_lower]

        # Add new keywords to the set
        for kw in found:
            seen_keywords.add(kw)

        cumulative.append(len(seen_keywords))

    return cumulative


# ---------------------------
# Compute curves for all datasets
# ---------------------------
curve_ransom = compute_saturation(df_ransom, "content", keywords)
curve_chain = compute_saturation(df_chain, "Message", keywords)
curve_reddit = compute_saturation(df_reddit, "merged_messages", keywords)

# ---------------------------
# Plot (full combined saturation curve)
# ---------------------------
plt.figure(figsize=(10, 6))

plt.plot(curve_ransom, label="Ransomware Notes Dataset")
plt.plot(curve_chain, label="ChainAbuse Reports Dataset")
plt.plot(curve_reddit, label="Reddit Blackmail Dataset")

plt.xlabel("Number of Report")
plt.ylabel("Cumulative Unique Theme Keywords Found")
plt.title("Combined Data Saturation Curve Across All Datasets")
plt.legend()
plt.grid(True)

plt.show()
