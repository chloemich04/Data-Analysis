import pandas as pd

# Load your Reddit dataset
df = pd.read_csv("/reddit.csv")

# Merge the three message fields into one
df["merged_messages"] = (
    df["message_1"].fillna("") + " " +
    df["message_2"].fillna("") + " " +
    df["message_3"].fillna("")
).str.strip()

# Optional: if you want to drop the originals
# df = df.drop(columns=["message_1", "message_2", "message_3"])

# Save the new file if needed
df.to_csv("reddit_dataset_clean.csv", index=False)
