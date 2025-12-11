import os

# Same roots as your main app
GAME_ROOTS = [
    r"G:\___ One-DVD READY GAMES ___",
    r"G:\___ Multi-DVD READY GAMES ___",
    r"G:\___ XBLA Games ___",
]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "my_xbox360_games.txt")

    titles = []

    for root in GAME_ROOTS:
        if not os.path.isdir(root):
            print(f"[WARN] Folder not found: {root}")
            continue

        category = os.path.basename(root.rstrip("\\/"))

        try:
            for entry in os.scandir(root):
                if entry.is_dir():
                    name = os.path.basename(entry.path)
                    titles.append((name, category, entry.path))
        except Exception as e:
            print(f"[ERROR] Could not read {root}: {e}")

    # Sort alphabetically by name
    titles.sort(key=lambda t: t[0].lower())

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("GameName\tCategory\tFullPath\n")
        for name, category, path in titles:
            f.write(f"{name}\t{category}\t{path}\n")

    print(f"Found {len(titles)} games.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
