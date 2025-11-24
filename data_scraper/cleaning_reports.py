import pandas as pd

df = pd.read_csv("chainabuse_reports.csv")

# Remove exact duplicate rows
df = df.drop_duplicates()

df.to_csv("chainabuse_reports_clean.csv", index=False)
print("Duplicates removed. Final size:", len(df))
