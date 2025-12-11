import csv
import os

INPUT_FILE = "games_list.csv"
OUTPUT_FILE = "game_sizes.csv"


def detect_delimiter(path):
    """Detect whether the file uses comma or tab as delimiter."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()

    # Prefer the one that appears more often
    comma_count = first_line.count(",")
    tab_count = first_line.count("\t")

    if tab_count > comma_count:
        delim = "\t"
    elif comma_count > 0:
        delim = ","
    else:
        # Fallback to comma if nothing obvious
        delim = ","

    print(f"Detected delimiter: {repr(delim)}")
    print(f"Raw header line: {first_line.strip()}")
    return delim


def get_folder_size(folder):
    total = 0
    for root, dirs, files in os.walk(folder):
        for name in files:
            full = os.path.join(root, name)
            try:
                total += os.path.getsize(full)
            except OSError:
                print(f"      ! Cannot read file: {full}")
    return total


def main():
    print("=== Xbox 360 Game Size Cache Builder ===")
    print(f"Current folder: {os.getcwd()}")
    print(f"Looking for input file: {INPUT_FILE}\n")

    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: {INPUT_FILE} not found in this folder.")
        return

    # Detect delimiter first
    delimiter = detect_delimiter(INPUT_FILE)

    # Read all rows using detected delimiter
    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        print("ERROR: games_list.csv is empty.")
        return

    # First row is header
    header_raw = rows[0]
    # Remove BOM if present
    header = [h.lstrip("\ufeff") for h in header_raw]

    print(f"\nDetected columns: {header}\n")

    try:
        idx_game = header.index("GameName")
        idx_cat = header.index("Category")
        idx_path = header.index("FullPath")
    except ValueError:
        print("ERROR: games_list.csv does not contain the expected columns.")
        print("Expected at least: GameName, Category, FullPath")
        print(f"Actual header: {header}")
        return

    data_rows = rows[1:]
    print(f"Read {len(data_rows)} rows from games_list.csv\n")

    output_rows = []
    processed = 0
    skipped_missing = 0
    skipped_empty = 0

    for idx, row in enumerate(data_rows, start=1):
        # Guard against short rows
        if len(row) <= idx_path:
            print(f"[{idx}] Skipping row with not enough columns: {row}")
            skipped_empty += 1
            continue

        game_name = (row[idx_game] or "").strip()
        category = (row[idx_cat] or "").strip()
        full_path = (row[idx_path] or "").strip().strip('"')

        if not full_path:
            print(f"[{idx}] Skipping row with empty FullPath: {row}")
            skipped_empty += 1
            continue

        if not os.path.exists(full_path):
            print(f"[{idx}] WARNING: Path does not exist, skipping: {full_path}")
            skipped_missing += 1
            continue

        print(f"[{idx}] Measuring: {game_name}")
        size_bytes = get_folder_size(full_path)

        output_rows.append({
            "GameName": game_name,
            "Category": category,
            "FullPath": full_path,
            "SizeBytes": size_bytes,
        })
        processed += 1

    # Write cache file as normal CSV (comma-separated)
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f_out:
        writer = csv.DictWriter(
            f_out,
            fieldnames=["GameName", "Category", "FullPath", "SizeBytes"],
            delimiter=",",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print("\n=== SUMMARY ===")
    print(f"Processed games: {processed}")
    print(f"Skipped (empty / bad row): {skipped_empty}")
    print(f"Skipped (missing path):    {skipped_missing}")
    print(f"\nCached sizes saved to: {OUTPUT_FILE}")
    print("You can now use game_sizes.csv in your main app for instant size lookups.")


if __name__ == "__main__":
    main()
