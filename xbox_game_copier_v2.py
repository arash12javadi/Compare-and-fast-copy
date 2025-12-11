import os
import shutil
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# >>>>> EDIT THESE IF YOUR DRIVE LETTER OR FOLDERS ARE DIFFERENT <<<<<
GAME_ROOTS = [
    r"G:\___ One-DVD READY GAMES ___",
    r"G:\___ Multi-DVD READY GAMES ___",
    r"G:\___ XBLA Games ___",
]

# Approx 2 TB in bytes (using 1024-based units)
TARGET_BYTES_2TB = 2 * 1024**4


def get_script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


COPIED_LOG_PATH = os.path.join(get_script_dir(), "copied_games_log.txt")
POPULAR_LIST_PATH = os.path.join(get_script_dir(), "popular_games.txt")


class GameItem:
    def __init__(self, name, full_path, category, var, checkbox):
        self.name = name
        self.full_path = full_path
        self.category = category
        self.var = var            # tk.BooleanVar for checkbox
        self.checkbox = checkbox  # ttk.Checkbutton widget
        self.size_bytes = None    # will be filled when needed
        self.copied = False       # set true if already copied


class XboxGameCopierApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Xbox 360 Game Selector (Python v2)")
        self.geometry("950x650")

        self.game_items = []
        self.copied_paths = set()

        self.search_var = tk.StringVar()

        self.load_copied_log()
        self.create_widgets()
        self.load_games()

    # ---------- UI SETUP ----------

    def create_widgets(self):
        # Top frame (info + search + refresh)
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        self.info_label = ttk.Label(top_frame, text="Select the games you want to copy.")
        self.info_label.pack(side=tk.LEFT)

        # Search box
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(10, 5))

        search_button = ttk.Button(top_frame, text="Search", command=self.search_games)
        search_button.pack(side=tk.LEFT, padx=2)

        clear_search_button = ttk.Button(top_frame, text="Clear", command=self.clear_search)
        clear_search_button.pack(side=tk.LEFT, padx=2)

        # Refresh
        refresh_button = ttk.Button(top_frame, text="Refresh List", command=self.load_games)
        refresh_button.pack(side=tk.RIGHT)

        # Middle frame: scrollable checkboxes
        middle_frame = ttk.Frame(self)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(middle_frame)
        self.scrollbar = ttk.Scrollbar(middle_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Bottom frame: buttons + status
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self.copy_button = ttk.Button(bottom_frame, text="Copy Selected to Folder...", command=self.copy_selected)
        self.copy_button.pack(side=tk.LEFT)

        self.size_button = ttk.Button(bottom_frame, text="Show Selected Size", command=self.show_selected_size)
        self.size_button.pack(side=tk.LEFT, padx=5)

        self.auto_select_button = ttk.Button(
            bottom_frame,
            text="Auto-select Popular (≈2 TB)",
            command=self.auto_select_popular_2tb
        )
        self.auto_select_button.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(bottom_frame, text="Ready.")
        self.status_label.pack(side=tk.LEFT, padx=10)

    # ---------- COPIED LOG ----------

    def load_copied_log(self):
        """Load previously-copied games from log file."""
        self.copied_paths.clear()
        if not os.path.isfile(COPIED_LOG_PATH):
            return

        try:
            with open(COPIED_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 1:
                        src_path = parts[0]
                        self.copied_paths.add(src_path)
        except Exception as e:
            messagebox.showwarning("Log error", f"Could not read copied log:\n{e}")

    def append_copied_log(self, src_path, dest_path):
        """Append one copied entry to log."""
        try:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(COPIED_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{src_path}|{dest_path}|{ts}\n")
        except Exception as e:
            messagebox.showwarning("Log error", f"Could not write to copied log:\n{e}")

    # ---------- GAME LIST LOADING ----------

    def clear_game_list(self):
        for child in self.inner_frame.winfo_children():
            child.destroy()
        self.game_items.clear()

    def load_games(self):
        self.clear_game_list()
        self.status_label.config(text="Loading games...")

        self.load_copied_log()

        row = 0
        total_games = 0

        for root in GAME_ROOTS:
            if not os.path.isdir(root):
                messagebox.showwarning("Folder not found", f"Folder not found:\n{root}")
                continue

            category = os.path.basename(root.rstrip("\\/"))

            try:
                for entry in os.scandir(root):
                    if entry.is_dir():
                        name = os.path.basename(entry.path)
                        var = tk.BooleanVar(value=False)

                        label_text = f"{name}    [{category}]"
                        if entry.path in self.copied_paths:
                            label_text += "   (COPIED)"

                        cb = ttk.Checkbutton(self.inner_frame, text=label_text, variable=var)
                        cb.grid(row=row, column=0, sticky="w", padx=5, pady=2)

                        game_item = GameItem(
                            name=name,
                            full_path=entry.path,
                            category=category,
                            var=var,
                            checkbox=cb
                        )

                        if entry.path in self.copied_paths:
                            game_item.copied = True
                            cb.state(["disabled"])

                        self.game_items.append(game_item)

                        row += 1
                        total_games += 1
            except Exception as e:
                messagebox.showerror("Error", f"Error reading folder {root}:\n{e}")

        if total_games == 0:
            self.status_label.config(text="No games found.")
        else:
            self.status_label.config(text=f"Loaded {total_games} games.")

    # ---------- SEARCH ----------

    def search_games(self):
        query = self.search_var.get().strip().lower()
        if not query:
            # show everything
            for g in self.game_items:
                g.checkbox.grid()  # restore previous position
            self.status_label.config(text="Search cleared (empty query).")
            return

        matches = 0
        for g in self.game_items:
            text = f"{g.name} {g.category}".lower()
            if query in text:
                g.checkbox.grid()
                matches += 1
            else:
                g.checkbox.grid_remove()

        self.status_label.config(text=f"Search: {matches} games match \"{self.search_var.get()}\".")

    def clear_search(self):
        self.search_var.set("")
        for g in self.game_items:
            g.checkbox.grid()
        self.status_label.config(text="Search cleared.")

    # ---------- SIZE CALCULATION ----------

    @staticmethod
    def get_dir_size(path):
        total = 0
        for root, dirs, files in os.walk(path):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total

    def show_selected_size(self):
        selected = [g for g in self.game_items if g.var.get()]
        if not selected:
            messagebox.showinfo("No selection", "No games selected.")
            return

        self.status_label.config(text="Calculating size of selected games...")
        self.update_idletasks()

        total_bytes = 0
        for g in selected:
            if g.size_bytes is None:
                g.size_bytes = self.get_dir_size(g.full_path)
            total_bytes += g.size_bytes

        gb = total_bytes / (1024**3)
        self.status_label.config(text=f"Selected size: ~{gb:.2f} GB ({total_bytes:,} bytes).")

        messagebox.showinfo(
            "Selected Size",
            f"Total size of selected games:\n\n"
            f"≈ {gb:.2f} GB\n({total_bytes:,} bytes)"
        )

    # ---------- AUTO-SELECT POPULAR ≈2 TB ----------

    def load_popular_list(self):
        if not os.path.isfile(POPULAR_LIST_PATH):
            messagebox.showwarning(
                "Popular list missing",
                f"No 'popular_games.txt' found.\n\n"
                f"Create it in:\n{POPULAR_LIST_PATH}\n\n"
                f"One game folder name per line."
            )
            return []

        names = []
        try:
            with open(POPULAR_LIST_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        names.append(line)
        except Exception as e:
            messagebox.showerror("Error", f"Error reading popular list:\n{e}")
            return []

        return names

    def auto_select_popular_2tb(self):
        popular_names = self.load_popular_list()
        if not popular_names:
            return

        # Map name -> index to preserve order
        name_order = {name.lower(): idx for idx, name in enumerate(popular_names)}

        # Candidates: games whose name is in popular list and not already copied
        candidates = [
            g for g in self.game_items
            if g.name.lower() in name_order and not g.copied
        ]

        if not candidates:
            messagebox.showinfo("No matches", "No games in the list match your popular_games.txt.")
            return

        # Sort by order in popular_games.txt
        candidates.sort(key=lambda g: name_order[g.name.lower()])

        # Now add them until we hit ~2TB
        total_bytes = 0
        added_count = 0

        self.status_label.config(text="Selecting popular games up to ≈2 TB...")
        self.update_idletasks()

        # First clear current selection
        for g in self.game_items:
            if not g.copied:
                g.var.set(False)

        for g in candidates:
            if g.copied:
                continue

            if g.size_bytes is None:
                g.size_bytes = self.get_dir_size(g.full_path)

            if total_bytes + g.size_bytes > TARGET_BYTES_2TB:
                # stop if adding this would exceed ~2TB
                continue

            g.var.set(True)
            total_bytes += g.size_bytes
            added_count += 1

        gb = total_bytes / (1024**3)

        messagebox.showinfo(
            "Auto-selection complete",
            f"Selected {added_count} popular games.\n"
            f"Approx total size: {gb:.2f} GB."
        )

        self.status_label.config(
            text=f"Auto-selected {added_count} popular games (~{gb:.2f} GB)."
        )

    # ---------- COPY SELECTED ----------

    def copy_selected(self):
        selected_games = [g for g in self.game_items if g.var.get() and not g.copied]

        if not selected_games:
            messagebox.showinfo(
                "No selection",
                "No games selected (or all selected games are already marked as copied)."
            )
            return

        dest_root = filedialog.askdirectory(title="Select destination folder for the selected games")
        if not dest_root:
            return  # user cancelled

        self.status_label.config(text="Copying... please wait.")
        self.copy_button.config(state=tk.DISABLED)
        self.size_button.config(state=tk.DISABLED)
        self.auto_select_button.config(state=tk.DISABLED)
        self.update_idletasks()

        success_count = 0
        fail_count = 0

        for g in selected_games:
            try:
                dest_dir = os.path.join(dest_root, g.name)
                dest_dir = self.get_unique_folder_path(dest_dir)

                self.copy_directory(g.full_path, dest_dir)

                # Mark as copied
                g.copied = True
                g.var.set(False)
                # Update label text to show COPIED
                text = g.checkbox.cget("text")
                if "(COPIED)" not in text:
                    g.checkbox.config(text=text + "   (COPIED)")
                g.checkbox.state(["disabled"])

                self.append_copied_log(g.full_path, dest_dir)

                success_count += 1
            except Exception as e:
                fail_count += 1
                messagebox.showerror("Copy error", f"Failed to copy \"{g.name}\":\n{e}")

        self.copy_button.config(state=tk.NORMAL)
        self.size_button.config(state=tk.NORMAL)
        self.auto_select_button.config(state=tk.NORMAL)

        self.status_label.config(text=f"Copy finished. Success: {success_count}, Failed: {fail_count}.")

        messagebox.showinfo(
            "Done",
            f"Copy finished.\n\nSuccessfully copied: {success_count}\nFailed: {fail_count}"
        )

    @staticmethod
    def get_unique_folder_path(base_path):
        if not os.path.exists(base_path):
            return base_path

        i = 1
        while True:
            new_path = f"{base_path} ({i})"
            if not os.path.exists(new_path):
                return new_path
            i += 1

    @staticmethod
    def copy_directory(src, dst):
        """Recursively copy folder src -> dst."""
        if not os.path.isdir(src):
            raise FileNotFoundError(f"Source directory does not exist: {src}")
        shutil.copytree(src, dst)


if __name__ == "__main__":
    app = XboxGameCopierApp()
    app.mainloop()
