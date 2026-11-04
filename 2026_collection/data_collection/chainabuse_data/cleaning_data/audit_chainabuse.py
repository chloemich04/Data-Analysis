import csv
import html
import re
from collections import Counter, defaultdict
from pathlib import Path


# Change this value when auditing another category.
category_name = "sextortion"

path = (
    Path(__file__).resolve().parent.parent
    / "raw_data"
    / "datasets"
    / "raw"
    / f"chainabuse_{category_name}.csv"
)

expected_category = category_name.replace("_", "-")

expected_header = [
    "report_id",
    "report_url",
    "category",
    "page_number",
    "card_position",
    "message_preview",
    "full_message",
    "message_length",
    "collected_at_utc",
]

# These patterns flag candidates for inspection.
tag_pattern = re.compile(r"</?[A-Za-z][^<>]*>")

entity_pattern = re.compile(
    r"&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);"
)

# Handles <br>, <br/>, <br />, and </br>.
break_pattern = re.compile(
    r"</?br\s*/?>(?:[ \t]*\n)?",
    flags=re.IGNORECASE,
)


# Read records and validate their structure.
reports = []
total_records = 0

with path.open(encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file, strict=True)
    header = next(reader, None)

    if header is None:
        raise ValueError(f"CSV file is empty: {path}")

    if header != expected_header:
        raise ValueError(f"Unexpected CSV header: {header!r}")

    previous_end = reader.line_num

    print(f"Source file: {path}")
    print("Columns:", header)

    for record_number, row in enumerate(reader, start=1):
        total_records += 1

        start_line = previous_end + 1
        end_line = reader.line_num
        previous_end = end_line

        if len(row) != len(header):
            raise ValueError(
                f"{path.name}: data record {record_number}, "
                f"lines {start_line}–{end_line}, "
                f"expected {len(header)} fields, found {len(row)}. "
                "Inspect this record before continuing."
            )

        reports.append(row)

print(f"\nTotal parsed records: {total_records}")
print(f"Records with expected field count: {len(reports)}")
print(f"Records with unexpected field count: {total_records - len(reports)}")
print(f"Reports available for further checks: {len(reports)}")

id_index = header.index("report_id")
message_index = header.index("full_message")
length_index = header.index("message_length")
category_index = header.index("category")


# Check repeated report IDs.
reports_by_id = defaultdict(list)

for report in reports:
    report_id = report[id_index]

    if report_id.strip():
        reports_by_id[report_id].append(report)

duplicate_id_groups = 0

for report_id, matching_reports in reports_by_id.items():
    if len(matching_reports) <= 1:
        continue

    duplicate_id_groups += 1
    differing_columns = []

    for column_index, column_name in enumerate(header):
        values = {
            report[column_index]
            for report in matching_reports
        }

        if len(values) > 1:
            differing_columns.append(column_name)

    print(f"\nRepeated report ID: {report_id}")
    print(f"Occurrences: {len(matching_reports)}")
    print(f"Columns with different values: {differing_columns}")

    for occurrence, report in enumerate(matching_reports, start=1):
        print(f"\n  Occurrence {occurrence}")

        for column_name in differing_columns:
            column_index = header.index(column_name)
            print(f"    {column_name}: {report[column_index]!r}")

print(f"\nRepeated ID groups: {duplicate_id_groups}")


# Compare full messages exactly as stored.
reports_by_message = defaultdict(list)

for report in reports:
    message = report[message_index]

    if message.strip():
        reports_by_message[message].append(report)

repeated_message_groups = 0
reports_in_repeated_groups = 0

for message, matching_reports in reports_by_message.items():
    if len(matching_reports) <= 1:
        continue

    repeated_message_groups += 1
    reports_in_repeated_groups += len(matching_reports)
    distinct_ids = {
        report[id_index]
        for report in matching_reports
    }

    print(f"\nRepeated message group {repeated_message_groups}")
    print(f"  Report occurrences: {len(matching_reports)}")
    print(f"  Distinct report IDs: {len(distinct_ids)}")

print(f"\nRepeated message groups: {repeated_message_groups}")
print(f"Reports in repeated message groups: {reports_in_repeated_groups}")

exact_row_repeats = len(reports) - len({
    tuple(report)
    for report in reports
})

print(f"Exact repeated rows beyond first occurrence: {exact_row_repeats}")


# Check empty and whitespace-only cells separately.
print("\nMissing-value check")

for column_index, column_name in enumerate(header):
    empty_count = 0
    whitespace_only_count = 0

    for report in reports:
        value = report[column_index]

        if value == "":
            empty_count += 1
        elif value.strip() == "":
            whitespace_only_count += 1

    print(
        f"  {column_name}: "
        f"{empty_count} empty, "
        f"{whitespace_only_count} whitespace-only"
    )


# Compare stored lengths using the observed newline convention.
print("\nMessage-length check")

invalid_lengths = 0
length_mismatches = 0

for report in reports:
    stored_length = report[length_index]

    try:
        expected_length = int(stored_length)
    except ValueError:
        invalid_lengths += 1
        print(
            f"  Invalid length for {report[id_index]}: "
            f"{stored_length!r}"
        )
        continue

    if expected_length < 0:
        invalid_lengths += 1
        print(
            f"  Negative length for {report[id_index]}: "
            f"{stored_length!r}"
        )
        continue

    normalized_message = report[message_index].replace("\r\n", "\n")
    actual_length = len(normalized_message)

    if expected_length != actual_length:
        length_mismatches += 1
        print(
            f"  Length mismatch for {report[id_index]}: "
            f"stored {expected_length}, calculated {actual_length}"
        )

print(f"Invalid length values: {invalid_lengths}")
print(f"Message-length mismatches: {length_mismatches}")


# Count messages containing each formatting feature.
print("\nMessage-formatting check")

formatting_counts = {
    "Multiline messages": 0,
    "Messages containing tabs": 0,
    "Leading or trailing whitespace": 0,
    "Unicode replacement characters": 0,
}

for report in reports:
    message = report[message_index]

    if "\n" in message or "\r" in message:
        formatting_counts["Multiline messages"] += 1

    if "\t" in message:
        formatting_counts["Messages containing tabs"] += 1

    if message != message.strip():
        formatting_counts["Leading or trailing whitespace"] += 1

    if "\ufffd" in message:
        formatting_counts["Unicode replacement characters"] += 1
        print(f"  Replacement character in report: {report[id_index]}")

for check_name, count in formatting_counts.items():
    print(f"  {check_name}: {count}")


# Compare category labels with the selected filename category.
print("\nCategory check")

category_counts = Counter(
    report[category_index]
    for report in reports
)

for category, count in category_counts.items():
    print(f"  {category!r}: {count}")

category_mismatches = sum(
    report[category_index] != expected_category
    for report in reports
)

print(f"Category mismatches: {category_mismatches}")


# Inspect possible markup and character references.
print("\nPossible HTML artifacts")

messages_with_tags = 0
messages_with_entities = 0

for report in reports:
    message = report[message_index]
    tags = tag_pattern.findall(message)
    entities = entity_pattern.findall(message)

    if tags:
        messages_with_tags += 1
        print(f"\n  Possible tags in report {report[id_index]}")
        print(f"    Matches: {tags[:5]!r}")

    if entities:
        messages_with_entities += 1
        print(f"\n  Possible entities in report {report[id_index]}")
        print(f"    Matches: {entities[:5]!r}")

print(f"\nMessages with possible tags: {messages_with_tags}")
print(f"Messages with possible entities: {messages_with_entities}")


# Show context around each distinct match within a report.
print("\nHTML match context")

for report in reports:
    message = report[message_index]
    seen_matches = set()

    for pattern in (tag_pattern, entity_pattern):
        for match in pattern.finditer(message):
            matched_text = match.group()

            if matched_text in seen_matches:
                continue

            seen_matches.add(matched_text)

            start = max(0, match.start() - 80)
            end = min(len(message), match.end() + 80)

            print(f"\n  Report ID: {report[id_index]}")
            print(f"  Match: {matched_text!r}")
            print(f"  Context: {message[start:end]!r}")


# Preview entity decoding in temporary strings.
print("\nEntity-decoding preview")

changed_messages = 0

for report in reports:
    original_message = report[message_index]

    if not entity_pattern.search(original_message):
        continue

    proposed_message = html.unescape(original_message)

    if proposed_message != original_message:
        changed_messages += 1
        print(f"\n  Report ID: {report[id_index]}")

        for entity in dict.fromkeys(
            entity_pattern.findall(original_message)
        ):
            print(f"    {entity!r} -> {html.unescape(entity)!r}")

print(f"\nMessages affected by entity decoding: {changed_messages}")


# Preview break conversion using the single pattern defined above.
print("\nLine-break conversion preview")
print(f"Active break pattern: {break_pattern.pattern}")
print(
    "Matches closing break tag:",
    break_pattern.fullmatch("</br>\n") is not None,
)

affected_messages = 0

for report in reports:
    original_message = report[message_index]
    normalized_message = original_message.replace("\r\n", "\n")
    match = break_pattern.search(normalized_message)

    if match is None:
        continue

    affected_messages += 1

    start = max(0, match.start() - 40)
    end = min(len(normalized_message), match.end() + 80)

    before = normalized_message[start:end]
    after = break_pattern.sub("\n", before)

    print(f"\n  Report ID: {report[id_index]}")
    print(f"  Before: {before!r}")
    print(f"  After:  {after!r}")

print(f"\nMessages affected by break conversion: {affected_messages}")