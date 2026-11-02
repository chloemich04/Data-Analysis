# Chainabuse bulk collector

Requires Python 3.10+, Selenium (`python -m pip install selenium`), and Chrome.
Run from a directory where `datasets/` should be created. No arguments opens the
original interactive single-page, range, and new-report-count modes.

1. Discover exact live category slugs:

   `python chainabuse_bulk_collector.py --discover-categories --headless`

2. Create `categories.json` with a `categories` array containing the exact slugs
   you want from that output. Category names from API documentation are not
   assumed to be website slugs. Bulk runs revalidate against live site links.

3. Measure a small real collection first:

   `python chainabuse_bulk_collector.py --bulk categories.json --benchmark --headless`

4. Resume a bounded bulk run:

   `python chainabuse_bulk_collector.py --bulk categories.json --max-pages 1000 --max-reports 10000 --max-seconds 14400 --workers 2 --interval 2 --headless`

Repeat the same command to resume. Limits apply per invocation; max-pages is per
category and max-reports counts new CSV rows across categories. Benchmark caps
these at 2 pages/category, 20 new rows, and 300 seconds; it saves real data and
advances the same checkpoint. It is not a throughput forecast.

Per-category CSV paths and column order match the original script, including
`full_message`. Only the full detail-description selector supplies that field;
previews are never substituted. Failure CSV headers are fixed. Run summaries,
including early stops, are printed and appended to `datasets/logs/chainabuse_runs.jsonl`.

The common path loads each listing once, snapshots public report links and
previews, then reads details in at most four isolated worker browsers. A global
minimum interval spaces navigation starts; retries also use it. JavaScript-only
cards fall back to Selenium clicks and listing reloads, so they will be slower.
Each worker owns its browser; only the coordinator writes output.

Completed pages are checkpointed atomically after CSV writes are synced. A
failed, interrupted, or partially saved page is replayed; existing CSV IDs are
skipped. Duplicate IDs are suppressed within each category, preserving category
membership across CSVs. Keep CSVs and checkpoints together. Do not edit either
while running. A local exclusive lock prevents simultaneous collectors in the
same datasets directory. After a hard crash, verify no collector is running
before removing the stale `datasets/raw/.collector.lock` file.

Ctrl+C, navigation timeouts, missing cards, repeated listing fingerprints,
pagination mismatches, report failures, access challenges, and configured limits
stop collection safely. A missing page is not marked complete. Read failure logs
and fix site/selector changes before resuming. Request limits and challenges are
not bypassed. Time limits are checked between operations; in-flight browser
operations may take their bounded timeouts before cleanup.

Listings change as new reports arrive: page checkpoints are not a snapshot of the
site. Periodically start a fresh checkpoint (`--checkpoint datasets/logs/rescan.json`)
from page zero while retaining CSVs to catch reports inserted on earlier pages.
No total report count or 200K throughput is guaranteed.

The script was syntax-checked locally. Live site collection, actual category
discovery, browser behavior, and throughput require a local benchmark run.
