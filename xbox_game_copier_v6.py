import os
import csv
import shutil
import time
import sys
import ctypes
from ctypes import wintypes
import subprocess
import tempfile

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# >>>>> EDIT THESE IF YOUR DRIVE LETTER OR FOLDERS ARE DIFFERENT <<<<<
GAME_ROOTS = [
    r"G:\___ One-DVD READY GAMES ___",
]
# GAME_ROOTS = [
#     r"G:\___ One-DVD READY GAMES ___",
#     r"G:\___ Multi-DVD READY GAMES ___",
#     r"G:\___ XBLA Games ___",
# ]


def get_script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


COPIED_LOG_PATH = os.path.join(get_script_dir(), "copied_games_log.txt")
POPULAR_LIST_PATH = os.path.join(get_script_dir(), "popular_games.txt")
GAME_SIZES_CSV_PATH = os.path.join(get_script_dir(), "game_sizes.csv")


class GameItem:
    def __init__(self, name, full_path, category, var, checkbox):
        self.name = name
        self.full_path = full_path
        self.category = category
        self.var = var            # tk.BooleanVar for checkbox
        self.checkbox = checkbox  # ttk.Checkbutton widget
        self.size_bytes = None    # set from cache or calculated
        self.copied = False       # from log / copy process
        self.exists_in_dest = False  # from destination scan


def load_size_cache():
    """
    Load game sizes from game_sizes.csv into a dict:
        normalized_full_path -> size_bytes (int)
    """
    cache = {}

    if not os.path.isfile(GAME_SIZES_CSV_PATH):
        print(f"[INFO] No game_sizes.csv found at {GAME_SIZES_CSV_PATH}. Size cache disabled.")
        return cache

    try:
        with open(GAME_SIZES_CSV_PATH, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()
            if "\t" in first_line:
                delim = "\t"
            elif ";" in first_line:
                delim = ";"
            else:
                delim = ","
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delim)

            for row in reader:
                full_path = (row.get("FullPath") or "").strip()
                size_str = (row.get("SizeBytes") or "").strip()
                if not full_path or not size_str:
                    continue

                try:
                    size_bytes = int(size_str)
                except ValueError:
                    continue

                norm = os.path.normcase(os.path.normpath(full_path))
                cache[norm] = size_bytes

        print(f"[INFO] Loaded {len(cache)} entries from game_sizes.csv")
    except Exception as e:
        print(f"[ERROR] Failed to load size cache: {e}")

    return cache


class XboxGameCopierApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Xbox 360 Game Selector (Python v6 – size cache + clipboard copy)")
        self.geometry("1000x680")

        self.game_items = []
        self.copied_paths = set()
        self.existing_names = set()  # from a scanned destination folder

        self.search_var = tk.StringVar()

        # size cache from game_sizes.csv
        self.size_cache = load_size_cache()

        self.load_copied_log()
        self.create_widgets()
        self.load_games()

    # ---------- UI SETUP ----------

    def create_widgets(self):
        # Top frame (info + search + refresh)
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        self.info_label = ttk.Label(
            top_frame,
            text="Select the games you want, then click 'Copy Selected to Clipboard' and paste in Explorer with Ctrl+V."
        )
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

        # Bottom frame: buttons + status + progress
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        # CHANGED: wording (functionality now copies to clipboard instead of disk)
        self.copy_button = ttk.Button(
            bottom_frame,
            text="Copy Selected to Clipboard",
            command=self.copy_selected
        )
        self.copy_button.pack(side=tk.LEFT)

        self.size_button = ttk.Button(bottom_frame, text="Show Selected Size", command=self.show_selected_size)
        self.size_button.pack(side=tk.LEFT, padx=5)

        # Auto-select popular with custom GB (using cache)
        self.auto_select_button = ttk.Button(
            bottom_frame,
            text="Auto-select Popular (by GB)...",
            command=self.auto_select_popular_dialog
        )
        self.auto_select_button.pack(side=tk.LEFT, padx=5)

        # Scan destination for existing games
        self.scan_dest_button = ttk.Button(
            bottom_frame,
            text="Scan Folder for Existing Games",
            command=self.scan_destination_for_existing
        )
        self.scan_dest_button.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(bottom_frame, text="Ready.")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Progress bar (now just used as a quick visual step, still kept)
        self.progress = ttk.Progressbar(
            bottom_frame,
            orient="horizontal",
            mode="determinate",
            length=220
        )
        self.progress.pack(side=tk.RIGHT, padx=5)

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

    @staticmethod
    def format_bytes(num_bytes):
        """Return a human-readable string for size."""
        if num_bytes is None:
            return ""
        gb = num_bytes / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.2f} GB"
        mb = num_bytes / (1024 ** 2)
        if mb >= 1:
            return f"{mb:.1f} MB"
        return f"{num_bytes} bytes"

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

                        # Try to get size from cache
                        norm = os.path.normcase(os.path.normpath(entry.path))
                        size_bytes = self.size_cache.get(norm)
                        size_str = f"   ({self.format_bytes(size_bytes)})" if size_bytes is not None else ""

                        label_text = f"{name}    [{category}]{size_str}"

                        # Mark if already copied via log
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

                        game_item.size_bytes = size_bytes  # from cache (may be None)

                        # Disable those already copied (from log)
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
                g.checkbox.grid()
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
            # Use cached size if available, otherwise compute and remember
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

    # ---------- POPULAR LIST ----------

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

    # ---------- AUTO-SELECT POPULAR BY GB (USING CACHE) ----------

    def auto_select_popular_dialog(self):
        """
        Ask the user for a target size in GB, e.g. 450, 850, 1800
        and then select popular games up to that size.
        """
        gb = simpledialog.askfloat(
            "Target size",
            "Enter target size in GB (e.g. 450, 850, 1800):",
            minvalue=1.0,
            maxvalue=5000.0,
            parent=self
        )
        if gb is None:
            return  # user cancelled

        target_bytes = int(gb * (1024**3))
        self.auto_select_popular(target_bytes, label=f"~{gb:.0f} GB")

    def auto_select_popular(self, target_bytes, label=""):
        popular_names = self.load_popular_list()
        if not popular_names:
            return

        # Map name -> index to preserve order
        name_order = {name.lower(): idx for idx, name in enumerate(popular_names)}

        # Candidates: games whose name is in popular list and not already copied
        candidates = [
            g for g in self.game_items
            if g.name.lower() in name_order and not g.copied and not g.exists_in_dest
        ]

        if not candidates:
            messagebox.showinfo("No matches", "No games in the list match your popular_games.txt.")
            return

        # Sort by order in popular_games.txt
        candidates.sort(key=lambda g: name_order[g.name.lower()])

        total_bytes = 0
        added_count = 0

        if label:
            self.status_label.config(text=f"Selecting popular games up to {label}...")
        else:
            self.status_label.config(text="Selecting popular games...")
        self.update_idletasks()

        # Clear current selection for games that are not already excluded
        for g in self.game_items:
            if not g.copied and not g.exists_in_dest:
                g.var.set(False)

        for g in candidates:
            if g.copied or g.exists_in_dest:
                continue

            # Use cached size if available, otherwise compute (once)
            if g.size_bytes is None:
                g.size_bytes = self.get_dir_size(g.full_path)

            if total_bytes + g.size_bytes > target_bytes:
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

        if label:
            self.status_label.config(
                text=f"Auto-selected {added_count} popular games ({label} target, picked ~{gb:.2f} GB)."
            )
        else:
            self.status_label.config(
                text=f"Auto-selected {added_count} popular games (~{gb:.2f} GB)."
            )

    # ---------- SCAN DESTINATION FOR EXISTING GAMES ----------

    def scan_destination_for_existing(self):
        """
        Ask user to select a folder on the new drive, list its subfolders as games,
        and disable any games in our list with exactly the same folder name.
        """
        dest_root = filedialog.askdirectory(
            title="Select folder on new drive to scan for existing games"
        )
        if not dest_root:
            return

        if not os.path.isdir(dest_root):
            messagebox.showerror("Error", "Selected path is not a directory.")
            return

        # Collect existing folder names (one level deep)
        existing_names = set()
        try:
            for entry in os.scandir(dest_root):
                if entry.is_dir():
                    existing_names.add(os.path.basename(entry.path).lower())
        except Exception as e:
            messagebox.showerror("Error", f"Error scanning destination folder:\n{e}")
            return

        if not existing_names:
            messagebox.showinfo("No folders", "No game folders found in the selected destination.")
            return

        self.existing_names = existing_names

        # Mark and disable matching games
        matches = 0
        for g in self.game_items:
            if g.name.lower() in existing_names:
                g.exists_in_dest = True
                g.var.set(False)
                text = g.checkbox.cget("text")
                if "(EXISTS)" not in text:
                    g.checkbox.config(text=text + "   (EXISTS)")
                g.checkbox.state(["disabled"])
                matches += 1

        messagebox.showinfo(
            "Scan complete",
            f"Found {len(existing_names)} folders in destination.\n"
            f"Disabled {matches} matching games in the list."
        )

        self.status_label.config(
            text=f"Destination scanned: {matches} games disabled as already existing."
        )

    # ---------- WINDOWS CLIPBOARD FILE COPY (NEW, POWERHELL-BASED) ----------

    def _copy_paths_to_windows_clipboard(self, paths):
        """
        Put a list of file/folder paths into the Windows clipboard as a FileDrop
        (same as Ctrl+C in Explorer) using PowerShell + .NET.

        On non-Windows systems, falls back to copying paths as plain text.
        """
        if not paths:
            return False

        # If not Windows, just copy as text
        if os.name != "nt":
            try:
                self.clipboard_clear()
                self.clipboard_append("\n".join(paths))
                self.update()  # keep clipboard after app closes
                messagebox.showinfo(
                    "Copied as text",
                    "Your OS is not Windows; folder paths were copied as plain text."
                )
                return True
            except Exception as e:
                messagebox.showerror("Clipboard error", f"Failed to copy text to clipboard:\n{e}")
                return False

        # Windows: use PowerShell + System.Windows.Forms.Clipboard.SetFileDropList
        try:
            # Write paths to a temporary UTF-8 text file (one path per line)
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                mode="w",
                encoding="utf-8"
            ) as tmp:
                temp_list_path = tmp.name
                for p in paths:
                    tmp.write(p + "\n")

            # Escape single quotes for PowerShell single-quoted string
            ps_path = temp_list_path.replace("'", "''")

            # PowerShell script:
            # - load System.Windows.Forms
            # - read the temp file lines
            # - put them into a StringCollection
            # - call Clipboard.SetFileDropList
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                f"$paths = Get-Content -LiteralPath '{ps_path}'; "
                "$col = New-Object System.Collections.Specialized.StringCollection; "
                "foreach ($p in $paths) { $col.Add($p) | Out-Null }; "
                "[System.Windows.Forms.Clipboard]::SetFileDropList($col);"
            )

            # Run PowerShell silently
            completed = subprocess.run(
                ["powershell", "-NoLogo", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True
            )

            # Clean up the temp file
            try:
                os.remove(temp_list_path)
            except OSError:
                pass

            if completed.returncode != 0:
                # Show any PowerShell error if present
                err_msg = completed.stderr.strip() or "Unknown PowerShell error"
                messagebox.showerror(
                    "Clipboard error",
                    f"Failed to copy to Windows clipboard via PowerShell:\n{err_msg}"
                )
                return False

            return True

        except Exception as e:
            messagebox.showerror("Clipboard error", f"Failed to copy to Windows clipboard:\n{e}")
            return False


    # ---------- COPY SELECTED (CHANGED TO CLIPBOARD) ----------

    def copy_selected(self):
        """
        NEW BEHAVIOUR in v6:

        - Takes selected games (not already copied / existing)
        - Puts their folder paths into the Windows clipboard as CF_HDROP
        - Marks them as copied and logs them (dest shown as <clipboard>)
        - User can then open any destination in Explorer and press Ctrl+V to paste
        """
        selected_games = [
            g for g in self.game_items
            if g.var.get() and not g.copied and not g.exists_in_dest
        ]

        if not selected_games:
            messagebox.showinfo(
                "No selection",
                "No games selected (or all selected games are already marked as copied/existing)."
            )
            return

        paths = [g.full_path for g in selected_games]

        self.status_label.config(text="Placing selected games into Windows clipboard...")
        self.copy_button.config(state=tk.DISABLED)
        self.size_button.config(state=tk.DISABLED)
        self.auto_select_button.config(state=tk.DISABLED)
        self.scan_dest_button.config(state=tk.DISABLED)

        # Progress bar is trivial here (single step)
        self.progress["value"] = 0
        self.progress["maximum"] = 1
        self.update_idletasks()

        success = self._copy_paths_to_windows_clipboard(paths)

        # Reset buttons
        self.copy_button.config(state=tk.NORMAL)
        self.size_button.config(state=tk.NORMAL)
        self.auto_select_button.config(state=tk.NORMAL)
        self.scan_dest_button.config(state=tk.NORMAL)

        if not success:
            self.status_label.config(text="Failed to set clipboard.")
            self.progress["value"] = 0
            return

        # Mark as copied & log (keeping your existing functionality)
        for g in selected_games:
            g.copied = True
            g.var.set(False)
            text = g.checkbox.cget("text")
            if "(COPIED)" not in text:
                g.checkbox.config(text=text + "   (COPIED)")
            g.checkbox.state(["disabled"])
            # We don't know the final destination folder here, so log <clipboard>
            self.append_copied_log(g.full_path, "<clipboard>")

        success_count = len(selected_games)
        self.progress["value"] = 1

        self.status_label.config(
            text=(
                f"Copied {success_count} games to clipboard. "
                f"Open your destination folder in File Explorer and press Ctrl+V to paste."
            )
        )
        messagebox.showinfo(
            "Copied to Clipboard",
            f"{success_count} game folder(s) have been placed on the Windows clipboard.\n\n"
            f"Now open your target folder in File Explorer and press Ctrl+V to start copying using Windows."
        )

        self.progress["value"] = 0

    # ---------- LEGACY UTIL (still here if needed later) ----------

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
        """Recursively copy folder src -> dst (kept for compatibility, unused in v6)."""
        if not os.path.isdir(src):
            raise FileNotFoundError(f"Source directory does not exist: {src}")
        shutil.copytree(src, dst)


if __name__ == "__main__":
    app = XboxGameCopierApp()
    app.mainloop()
