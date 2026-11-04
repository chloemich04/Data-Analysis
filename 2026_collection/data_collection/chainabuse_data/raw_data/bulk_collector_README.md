<div align="center">

# 🛡️ Chainabuse Bulk Report Collector

**Research-focused · Resumable · Category-based · CSV-ready**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-Browser%20Automation-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Output](https://img.shields.io/badge/Output-CSV%20%2B%20JSON-155E75?style=for-the-badge)
![Purpose](https://img.shields.io/badge/Purpose-Scam%20Research-1D4ED8?style=for-the-badge)

*A practical guide for collecting and managing publicly visible scam reports for research.*

</div>

---

> [!IMPORTANT]
> **Research use only.** Respect the site's access requirements, challenges, and rate limits. Treat report narratives as potentially sensitive and review personal identifiers before sharing data.

## 📑 Contents

- [Overview](#-overview)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Choose a scenario](#-choose-a-scenario)
- [How it works](#-how-it-works)
- [Files and data fields](#-files-and-data-fields)
- [CLI reference](#-cli-reference)
- [Troubleshooting](#-troubleshooting)
- [Research workflow](#-research-workflow)

---

## 🔎 Overview

A Python/Selenium research utility for collecting publicly visible Chainabuse scam reports by category. It saves the **full report description** (not just the listing preview), alongside the report URL, identifier, category, and collection metadata. The collector supports interactive single-category runs and command-line bulk collection, with deduplication, checkpoints, retry tracking, and run summaries.


## 🧰 Requirements

- Python 3.10+ (recommended)
- Google Chrome installed
- Selenium (`pip install selenium`)
- Internet access to Chainabuse; a valid account if the site requires sign-in

Selenium Manager normally handles the matching ChromeDriver automatically. The script uses Python standard-library modules for its other dependencies.

## ⚙️ Installation

Open PowerShell in the directory containing `chainabuse_bulk_collector.py`:

```powershell
cd "C:\path\to\your\project"
python -m pip install selenium
python chainabuse_bulk_collector.py --help
```

If `python` is unavailable on Windows, try `py` instead. All examples below assume `python` works.

## 🚀 Choose a scenario

| Scenario | Command |
| --- | --- |
| Open the original interactive menu | `python chainabuse_bulk_collector.py` |
| Small benchmark, Other Blackmail | `python chainabuse_bulk_collector.py --category other-blackmail --benchmark` |
| Small benchmark **with manual login** | `python chainabuse_bulk_collector.py --category other-blackmail --benchmark --login` |
| Collect up to 1,000 new reports from at most 100 pages | `python chainabuse_bulk_collector.py --category other-blackmail --max-pages 100 --max-reports 1000 --max-seconds 3600` |
| Same collection **with login** | `python chainabuse_bulk_collector.py --category other-blackmail --max-pages 100 --max-reports 1000 --max-seconds 3600 --login` |
| Discover currently linked category slugs | `python chainabuse_bulk_collector.py --discover-categories --login` |
| Run a configured set of categories | `python chainabuse_bulk_collector.py --bulk categories.json --login --max-pages 100 --max-reports 1000` |
| Run without showing Chrome (only when login is not needed) | `python chainabuse_bulk_collector.py --category other-blackmail --benchmark --headless` |

### 🧪 Scenario 1 — Check that extraction works before a long run

```powershell
python chainabuse_bulk_collector.py --category other-blackmail --benchmark --login
```

> [!NOTE]
> `--benchmark` **still collects and saves real reports**.

 It caps the run at **2 pages per category, 20 new reports total, and 5 minutes**, whichever limit is reached first. Examine the CSV and the terminal's `reports_per_minute`, `failures`, and `stop_reason` before scaling up.

### 🔑 Scenario 2 — Sign in manually

Append `--login` to a command:

```powershell
python chainabuse_bulk_collector.py --category other-blackmail --max-pages 100 --max-reports 1000 --login
```

1. Chrome opens and navigates to the Chainabuse reports page.
2. Sign in **inside that Chrome window** using the site's normal login flow.
3. Return to PowerShell and press **Enter** after signing in.
4. The collector starts its run.

`--login` uses **one worker** and the authenticated browser session. Do **not** combine `--login` and `--headless`; the script rejects that combination. Credentials are entered in Chrome, not passed as CLI arguments or saved by this script.

**Note:** Running without arguments opens the legacy interactive menu. To use the command-line login workflow, provide at least `--login` (and preferably `--category` or other limits).

### 📦 Scenario 3 — Collect a single category in a longer run

```powershell
python chainabuse_bulk_collector.py --category other-blackmail --start-page 0 --max-pages 100 --max-reports 1000 --max-seconds 3600 --login
```

- `--start-page 0` means the **first** website page; command-line page indexes start at zero.
- `--max-pages 100` is the maximum number of listing pages to examine **for this invocation**.
- `--max-reports 1000` limits **new saved rows across all selected categories**.
- `--max-seconds 3600` limits collection to approximately one hour (the manual login wait is excluded).

These are upper bounds, not guarantees. The collector can stop earlier because of a repeated listing, a loading problem, an access challenge, or another safety condition.

### 🗂️ Scenario 4 — Collect several categories in one run

First, discover the category identifiers actually linked on the website:

```powershell
python chainabuse_bulk_collector.py --discover-categories --login
```

Create a `categories.json` file beside the script. Replace the placeholders below with **exact category slugs returned by discovery**:

```json
{
  "categories": [
    "other-blackmail",
    "REPLACE_WITH_VERIFIED_CATEGORY_SLUG"
  ]
}
```

Remove the placeholder if collecting only `other-blackmail`. Then run:

```powershell
python chainabuse_bulk_collector.py --bulk categories.json --login --max-pages 100 --max-reports 1000 --max-seconds 3600
```

The script verifies each configured slug against live-discovered categories. It processes categories sequentially and saves a **separate CSV per category**. The `--max-reports` and `--max-seconds` limits apply to the **whole invocation**, not individually to each category; a limit can be reached before later categories are processed.

### ♻️ Scenario 5 — Resume after an interruption

Run the **same command again**, keeping the same checkpoint path and output directory:

```powershell
python chainabuse_bulk_collector.py --category other-blackmail --max-pages 100 --max-reports 1000 --login
```

The collector reads existing CSV report IDs to avoid duplicate rows and uses its checkpoint to continue from the saved page. If a page was only partially processed, it may be replayed. Failed report URLs are retained in a pending-retry queue.

> [!WARNING]
> `--max-pages` is a per-invocation window beginning at the resumed page; it is **not** a total lifetime page cap. Pagination can shift as new reports are published, so checkpoints do not prove exhaustive historical coverage. For an intentional rescan, use a **different** `--checkpoint` filename and keep the existing CSVs for deduplication; do not delete raw data.

### 🧭 Scenario 6 — Use a different checkpoint for a separate experiment

```powershell
python chainabuse_bulk_collector.py --category other-blackmail --benchmark --login --checkpoint datasets/logs/benchmark_checkpoint.json
```

This keeps the experiment's page progress separate from the default bulk checkpoint. The output CSV is still shared, so existing report IDs will be skipped.

## 🔄 How it works

1. Open the selected category listing page in Chrome.
2. Read the report previews and look for report-detail links in the listing HTML.
3. If a link is unavailable, use a visible card click to discover its URL, then return to the listing.
4. Skip report IDs already saved in the category CSV.
5. Open remaining report details, extract the full description, and append the row.
6. Log failures, retain unresolved report URLs for retry, and save checkpoint progress.
7. Print a JSON run summary with elapsed time, saved reports, duplicates, failures, navigation count, and throughput.

The optimized collector uses up to **4 detail workers** when not in login mode; default is **2**. Navigation is paced across workers with a global minimum interval (default **2 seconds**). It stops rather than trying to bypass access challenges.

## 📁 Files and data fields

Files are created relative to the **directory from which you run the command**:

```text
project-folder/
├── chainabuse_bulk_collector.py
├── categories.json                  # optional, created by you
└── datasets/
    ├── raw/
    │   ├── chainabuse_other_blackmail.csv
    │   └── chainabuse_<other_category>.csv
    └── logs/
        ├── chainabuse_failures.csv
        ├── chainabuse_checkpoint.json
        ├── chainabuse_runs.jsonl
        ├── chainabuse_links/         # cached discovered links, by category/page
        └── interactive_*.json        # checkpoints for legacy menu runs
```

### 🧬 Raw CSV columns

| Column | Meaning |
| --- | --- |
| `report_id` | Identifier extracted from the report URL |
| `report_url` | Canonical report detail URL |
| `category` | Category slug used for collection |
| `page_number` | Zero-based category page at collection time |
| `card_position` | One-based position on the listing page |
| `message_preview` | Preview shown on the listing |
| `full_message` | Full description extracted from the detail page |
| `message_length` | Character count of `full_message` |
| `collected_at_utc` | UTC collection timestamp |

The raw dataset preserves the extracted text. Do filtering, normalization, anonymization, and coding in **separate derived files**, not by overwriting these raw CSVs. The same report can appear in more than one category CSV if the site categorizes it that way.

### 📝 Failure and progress logs

- `chainabuse_failures.csv` records category, page, card position, URL, error type, error message, and timestamp.
- `chainabuse_checkpoint.json` stores next-page progress and pending reports for retry.
- `chainabuse_runs.jsonl` appends one JSON summary per invocation.
- `chainabuse_links/` caches report links for listing pages where card-click discovery was needed.

## 🧾 CLI reference

| Option | Default | Description |
| --- | --- | --- |
| `--category SLUG` | `other-blackmail` | One category |
| `--bulk FILE` | — | JSON file containing `{"categories": [...]}` |
| `--discover-categories` | Off | Print category slugs linked by the site |
| `--start-page N` | `0` | Zero-based first page |
| `--max-pages N` | `100` | Maximum pages per category this invocation |
| `--max-reports N` | `1000` | Maximum new rows across the invocation |
| `--max-seconds N` | `3600` | Collection time limit, seconds |
| `--workers N` | `2` | Detail browsers, 1–4; forced to 1 with login |
| `--interval N` | `2.0` | Minimum seconds between navigation starts; at least 1 |
| `--retries N` | `1` | Additional detail navigation attempts, 0–3 |
| `--checkpoint PATH` | `datasets/logs/chainabuse_checkpoint.json` | Progress file |
| `--login` | Off | Manual sign-in in visible Chrome |
| `--headless` | Off | Hide Chrome; incompatible with login |
| `--benchmark` | Off | Cap at 2 pages/category, 20 new rows, 300 seconds |
| `--help` | — | Print CLI help |

For example, a conservative single-worker test without login:

```powershell
python chainabuse_bulk_collector.py --category other-blackmail --benchmark --workers 1 --interval 3
```

## 🛠️ Troubleshooting

**`ModuleNotFoundError: No module named 'selenium'`**  
Install it in the same Python environment: `python -m pip install selenium`.

**Chrome does not start**  
Check that Chrome is installed and updated and that Selenium can obtain a compatible driver. Try the visible benchmark before using `--headless`.

**The site asks me to sign in**  
Add `--login`, sign in through the Chrome window, and press Enter in PowerShell only after authentication completes.

**`--login` cannot be used with `--headless`**  
Remove `--headless` from the command.

**The run saves zero reports**  
Check `stop_reason` in the printed JSON summary and inspect the CSV/checkpoint. The selected pages may already be collected, or the page may have failed to load. `--benchmark` counts **new** rows, not all rows seen.

**The run stops on an access challenge or rate limit**  
Do not attempt to bypass the challenge. Wait, check the site's access requirements, and reduce request frequency before retrying if permitted.

**`FileExistsError` mentions `.collector.lock`**  
Only one collector process should write the dataset at a time. Confirm no collector is still running. If a previous process crashed and the lock is stale, remove `datasets/raw/.collector.lock` **only after confirming no collector process is active**.

**The output folder is not where I expected**  
Run the command from the intended project directory. Relative output paths are based on the terminal's working directory.

**I need to start from page 1 again**  
The CLI calls that `--start-page 0`. To rescan without reusing the previous progress pointer, provide a new `--checkpoint` path. Existing CSV IDs still prevent duplicate saves.

## 🔐 Research and data-quality notes

- A successful run is **not proof that every category report was captured**; dynamic pagination, access restrictions, changing site markup, and retries can affect completeness.
- Review `chainabuse_failures.csv` and pending reports before analyzing coverage.
- Verify that `full_message` contains the expected text; the collector deliberately rejects empty descriptions instead of silently replacing them with previews.
- Record the category list, collection dates, commands, and stop reasons in your research methodology.
- Preserve raw text separately from filtered/anonymized datasets. Publicly posted scam reports may still contain personal or sensitive information.

## 🎓 Research workflow

1. Run an authenticated benchmark and inspect the saved narratives.
2. Discover categories and build `categories.json` with the verified slugs relevant to the study.
3. Run bounded bulk sessions, periodically reviewing throughput and failures.
4. Re-run the same command to resume unfinished collection.
5. Copy the raw CSVs into a separate analysis workspace and begin filtration, deduplication across sources, anonymization, and codebook development.

> [!NOTE]
> **Current implementation note:** The script uses Selenium/Chrome for collection; it does not implement an HTTP-only downloader or guarantee that 200,000 reports can be collected within a particular timeframe. Benchmark the actual reports-per-minute rate before planning a full crawl.

---

<div align="center">

**Built for reproducible data collection and responsible research.**

</div>
