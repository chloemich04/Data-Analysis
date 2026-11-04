import argparse
import csv
import hashlib
import html
import json
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


HEADER = [
    "report_id", "report_url", "category", "page_number", "card_position",
    "message_preview", "full_message", "message_length", "collected_at_utc",
]

CATEGORIES = [
    "impersonation", "other_blackmail", "other_investment_scam",
    "ransomware", "romance", "sextortion",
]

EXCLUDED_ID = "3e928e4a-0689-407d-af64-47b391314dc4"
FIRST_REPAIR_ID = "6163bed2-18c6-4310-97ec-70a117353920"
BREAK_PATTERN = re.compile(r"</?br\s*/?>(?:[ \t]*\n)?", re.IGNORECASE)


def clean_message(original):
    changes = []
    normalized = original.replace("\r\n", "\n")

    if normalized != original:
        changes.append("normalized_crlf_to_lf")

    converted = BREAK_PATTERN.sub("\n", normalized)

    if converted != normalized:
        changes.append("converted_html_breaks")

    cleaned = html.unescape(converted)

    if cleaned != converted:
        changes.append("decoded_html_entities_once")

    return cleaned, changes


def read_reports(path, category):
    reports = []
    repairs = []
    parsed_count = 0

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, strict=True)

        if next(reader, None) != HEADER:
            raise ValueError(f"Unexpected or missing header in {path}")
        
        previous_end = reader.line_num

        for record_number, row in enumerate(reader, 1):
            parsed_count += 1
            start_line = previous_end + 1
            end_line = reader.line_num
            previous_end = end_line

            source = {
                "source_file": path.name,
                "source_record": record_number,
                "source_start_line": start_line,
                "source_end_line": end_line,
            }
            reconstructed = [row]

            if len(row) != len(HEADER):
                if not (category == "ransomware" and len(row) == 17
                        and row[0] == FIRST_REPAIR_ID
                        and row[8].endswith(EXCLUDED_ID)):
                    raise ValueError(f"Unreviewed malformed record in {path}: {source}")
                
                timestamp = row[8][:-36]
                second_id = row[8][-36:]
                datetime.fromisoformat(timestamp)
                UUID(second_id)
                
                if row[9].split("?")[0] != f"https://chainabuse.com/report/{second_id}":
                    raise ValueError("Repair ID does not match its report URL")
                
                reconstructed = [row[:8] + [timestamp], [second_id] + row[9:]]
                
                repairs.append({**source, "action": "split_joined_records",
                                "original_fields": 17, "resulting_records": 2,
                                "report_ids": [FIRST_REPAIR_ID, second_id]})
                
            for values in reconstructed:
                report = dict(zip(HEADER, values))

                if report["category"] != category.replace("_", "-"):
                    raise ValueError(f"Category mismatch: {source}")
                
                if any(not value.strip() for value in values):
                    raise ValueError(f"Unreviewed blank value: {source}")
                
                actual_length = len(report["full_message"].replace("\r\n", "\n"))

                if int(report["message_length"]) != actual_length:
                    raise ValueError(f"Message length mismatch: {source}")
                
                reports.append((report, source))

    return reports, repairs, parsed_count


def write_verified_csv(path, rows, columns):
    with path.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        saved = list(reader)
        expected = [{key: str(row[key]) for key in columns} for row in rows]

        if reader.fieldnames != columns or saved != expected:
            raise ValueError(f"Read-back verification failed: {path}")


def main():
    parser = argparse.ArgumentParser(description="Apply reviewed Chainabuse cleaning rules.")
    
    parser.add_argument("--raw-dir", type=Path, default=(
        Path(__file__).resolve().parent.parent / "raw_data" / "datasets" / "raw"
    ))
    
    parser.add_argument("--output-dir", type=Path, default=(
        Path(__file__).resolve().parent / "outputs"
    ))
    
    args = parser.parse_args()
    
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "categories": [], "repairs": [], "exclusions": [],
                "text_changes": [], "review_flags": []}
    
    prepared = {}
    
    for category in CATEGORIES:
        path = args.raw_dir / f"chainabuse_{category}.csv"
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        reports, repairs, parsed_count = read_reports(path, category)

        manifest["repairs"].extend(repairs)

        id_counts = Counter(report["report_id"] for report, source in reports)
        message_counts = Counter(report["full_message"] for report, source in reports)
        cleaned_rows = []

        for report, source in reports:
            report_id = report["report_id"]

            if category == "ransomware" and report_id == EXCLUDED_ID:
                manifest["exclusions"].append({**source, **report,
                    "reason": "Excluded after manual review by researcher"})
                
                continue

            cleaned, changes = clean_message(report["full_message"])

            flags = []
            
            if id_counts[report_id] > 1:
                flags.append("repeated_report_id")

            if message_counts[report["full_message"]] > 1:
                flags.append("exact_message_shared")

            if "\ufffd" in report["full_message"]:
                flags.append("replacement_character_requires_source_review")

            if any(character in report["full_message"] for character in "\u200b\u200c\u200d\ufeff"):
                flags.append("invisible_unicode_preserved")

            cleaned_rows.append({**report, "full_message_clean": cleaned,
                                 "message_length_clean": len(cleaned)})
            
            if changes:
                manifest["text_changes"].append({**source, "report_id": report_id,
                    "changes": changes, "original_character_count": len(report["full_message"]),
                    "cleaned_character_count": len(cleaned)})
                
            if flags:
                manifest["review_flags"].append({**source, "report_id": report_id, "flags": flags})
        
        prepared[category] = cleaned_rows
        
        manifest["categories"].append({"category": category, "source_path": str(path.resolve()),
            "source_sha256": source_hash, "parsed_records": parsed_count,
            "reconstructed_occurrences": len(reports), "retained_reports": len(cleaned_rows),
            "excluded_occurrences": len(reports) - len(cleaned_rows)})
        
        if hashlib.sha256(path.read_bytes()).hexdigest() != source_hash:
            raise ValueError(f"Source changed during processing: {path}")

    # Publish the complete, verified collection only after every file is ready.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_name = "cleaned_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination = args.output_dir / run_name
    
    with tempfile.TemporaryDirectory(prefix=".preparing_", dir=args.output_dir) as temporary:
        staging = Path(temporary) / "dataset"
        staging.mkdir()
        
        for category, rows in prepared.items():
            write_verified_csv(staging / f"chainabuse_{category}_cleaned.csv", rows,
                               HEADER + ["full_message_clean", "message_length_clean"])
        
        log_path = staging / "cleaning_log.json"
        
        log_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        
        if json.loads(log_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Log read-back verification failed")
        
        staging.rename(destination)

    for item in manifest["categories"]:
        print(f"{item['category']}: {item['retained_reports']} verified saved reports")
    
    print(f"Dataset folder: {destination.resolve()}")


if __name__ == "__main__":
    main()
