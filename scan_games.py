import csv
import os

# =======================
# CONFIGURE YOUR FOLDERS
# =======================
GAME_ROOTS = [
    ("XBLA",      r"G:\___ XBLA Games ___"),
    ("1DVD",      r"G:\___ One-DVD READY GAMES ___"),
    ("MultiDVD",  r"G:\___ Multi-DVD READY GAMES ___"),
    # add more if you want
    # ("PS1",       r"G:\___ OTHER CONSOLE GAMES ___\PS1 Games"),
]

OUTPUT_FILE = "games_list.csv"

def main():
    print("=== Xbox 360 Game Scanner ===")
    rows = []

    for category, root in GAME_ROOTS:
        print(f"\nScanning category '{category}' in: {root}")
        if not os.path.isdir(root):
            print(f"  !! SKIPPING: folder does not exist: {root}")
            continue

        # Each immediate subfolder is treated as one game
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue

            game_name = entry.name
            full_path = entry.path

            rows.append({
                "GameName": game_name,
                "Category": category,
                "FullPath": full_path,
            })
            print(f"  Found game: {game_name}")

    if not rows:
        print("\nNo games found. Please check the GAME_ROOTS paths.")
        return

    # Write COMMA-separated CSV for better Excel compatibility
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["GameName", "Category", "FullPath"],
            delimiter=",",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDONE. Wrote {len(rows)} games to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
