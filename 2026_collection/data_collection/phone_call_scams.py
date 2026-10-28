import pandas as pd

# Read the CSV file from the Hugging Face dataset
df = pd.read_csv("hf://datasets/BothBosu/Scammer-Conversation/gen_conver_noIdentifier_1000.csv")

# Save the DataFrame to a local CSV file -> named "phone_call_scams.csv" (need to modify the file for further processing)
df.to_csv("2026_collection/data_collection/phone_call_scams.csv", index=False)