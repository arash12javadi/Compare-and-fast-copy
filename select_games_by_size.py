import csv
import os

INPUT_FILE = "game_sizes.csv"
OUTPUT_FILE = "popular_games.txt"

# Category priority:
# Higher number = picked earlier.
CATEGORY_PRIORITY = {
    "MultiDVD": 4,
    "Multi-DVD": 4,
    "2DVD": 4,
    "2-DVD": 4,
    "1DVD": 3,
    "One-DVD": 3,
    "1-DVD": 3,
    "DVD": 2,
    "XBLA": 1,
}


def parse_size_input(size_str: str) -> float:
    """
    Parse a user input like:
    450       -> 450 GB
    450gb     -> 450 GB
    1.8tb     -> 1.8 * 1024 GB
    20 g      -> 20 GB
    Returns value in GB (float).
    """
    s = size_str.strip().lower().replace(" ", "")
    if not s:
        raise ValueError("Empty size string")

    # Detect unit
    if s.endswith("tb"):
        num_part = s[:-2]
        factor = 1024.0  # TB -> GB
    elif s.endswith("gb"):
        num_part = s[:-2]
        factor = 1.0     # GB
    else:
        # No unit: assume GB
        num_part = s
        factor = 1.0

    value = float(num_part)
    return value * factor


def read_games_with_sizes(path: str):
    if not os.path.exists(path):
        print(f"ERROR: {path} not found.")
        return []

    games = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            try:
                size_bytes = int(row.get("SizeBytes", "0") or 0)
            except ValueError:
                size_bytes = 0

            games.append({
                "GameName": row.get("GameName", "").strip(),
                "Category": row.get("Category", "").strip(),
                "FullPath": row.get("FullPath", "").strip().strip('"'),
                "SizeBytes": size_bytes,
            })

    return games


def category_score(category: str) -> int:
    """
    Return priority score for category.
    Higher score -> earlier in the list.
    Unknown categories get 0.
    """
    return CATEGORY_PRIORITY.get(category, 0)


def pick_games_for_budget(games, target_gb: float):
    """
    games: list of dicts with SizeBytes, Category, etc.
    target_gb: desired total in GB.
    Returns (picked_games, total_gb).
    """
    # Sort:
    #   1) by category priority (descending)
    #   2) by size (descending)
    sorted_games = sorted(
        games,
        key=lambda g: (category_score(g["Category"]), g["SizeBytes"]),
        reverse=True,
    )

    picked = []
    total_bytes = 0
    target_bytes = int(target_gb * (1024**3))

    for g in sorted_games:
        size = g["SizeBytes"]
        if size <= 0:
            continue

        if total_bytes + size > target_bytes:
            # If adding this game would massively overshoot and we already have something, skip it
            # Try to keep total under or close to the target
            continue

        picked.append(g)
        total_bytes += size

    total_gb = total_bytes / (1024**3)
    return picked, total_gb


def write_popular_list(picked, total_gb: float, size_request_gb: float):
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        f.write("# Selected Xbox 360 games\n")
        f.write(f"# Requested size: ~{size_request_gb:.2f} GB\n")
        f.write(f"# Actual total : {total_gb:.2f} GB\n\n")
        f.write("GameName\tCategory\tSizeGB\tFullPath\n")

        for g in picked:
            size_gb = g["SizeBytes"] / (1024**3)
            line = f"{g['GameName']}\t{g['Category']}\t{size_gb:.2f}\t{g['FullPath']}\n"
            f.write(line)


def main():
    print("=== Xbox 360 Popular Games Picker ===")
    print(f"Current folder: {os.getcwd()}")
    print(f"Reading size cache from: {INPUT_FILE}\n")

    games = read_games_with_sizes(INPUT_FILE)
    if not games:
        print("ERROR: No games loaded from size cache.")
        return

    print(f"Loaded {len(games)} games from cache.\n")

    # Ask user for size
    print("Enter desired total size for selection, e.g.:")
    print("  450      -> 450 GB")
    print("  850gb    -> 850 GB")
    print("  1.8tb    -> approx 1843 GB")
    print("  20gb     -> 20 GB\n")

    user_input = input("Target size (GB/TB): ").strip()
    try:
        target_gb = parse_size_input(user_input)
    except Exception as e:
        print(f"ERROR: Could not parse size '{user_input}': {e}")
        return

    print(f"\nPicking games up to ~{target_gb:.2f} GB...\n")
    picked, total_gb = pick_games_for_budget(games, target_gb)

    if not picked:
        print("No games could be picked for this budget (maybe too small?).")
        return

    write_popular_list(picked, total_gb, target_gb)

    print(f"Selected {len(picked)} games.")
    print(f"Total size: {total_gb:.2f} GB (requested ~{target_gb:.2f} GB)")
    print(f"Written to: {OUTPUT_FILE}")
    print("\nYou can now open popular_games.txt and use it to copy those folders.")


if __name__ == "__main__":
    main()
