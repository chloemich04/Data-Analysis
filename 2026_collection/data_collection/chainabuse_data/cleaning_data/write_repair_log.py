import csv
from pathlib import Path

output_directory = Path(__file__).resolve().parent / "outputs"
repair_path = output_directory / "chainabuse_ransomware_repairs.csv"

repair = {
    "source_file": "chainabuse_ransomware.csv",
    "source_record": 14,
    "source_start_line": 95,
    "source_end_line": 105,
    "original_field_count": 17,
    "reconstructed_report_count": 2,
    "first_report_id": "6163bed2-18c6-4310-97ec-70a117353920",
    "second_report_id": "3e928e4a-0689-407d-af64-47b391314dc4",
    "action": "split_joined_records",
    "details": (
        "Separated the first collection timestamp from the second report UUID. "
        "Validated timestamp format, UUID format, and second report URL. "
        "Reconstructed two nine-field records before applying exclusions."
    ),
}

with repair_path.open("x", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(repair))
    writer.writeheader()
    writer.writerow(repair)

print(f"Repair log saved: {repair_path}")