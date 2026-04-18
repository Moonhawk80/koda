"""
Koda Usage Stats Dashboard — visual breakdown of voice input usage.
"""

import tkinter as tk
from tkinter import ttk
import threading


class StatsDashboard:
    """Usage stats window accessible from tray menu."""

    def __init__(self):
        self._thread = None

    def show(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        from ui_theme import apply_dark_theme, BG, BG_ALT, FG_PRIMARY, FG_GREEN, FG_MUTED

        root = tk.Tk()
        root.title("Koda — Usage Stats")
        root.geometry("500x580")
        root.resizable(False, False)

        style = apply_dark_theme(root, header_size=14)
        # stats-specific extras (not shared with other dark-theme windows)
        style.configure("Big.TLabel", background=BG, foreground=FG_GREEN, font=("Segoe UI", 24, "bold"))
        style.configure("Unit.TLabel", background=BG, foreground=FG_MUTED, font=("Segoe UI", 9))
        style.configure("Stat.TLabel", background=BG_ALT, foreground=FG_PRIMARY, font=("Segoe UI", 10))

        main = ttk.Frame(root, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Usage Stats", style="Header.TLabel").pack(anchor="w", pady=(0, 15))

        # Load stats
        try:
            from stats import get_summary, get_today_summary, init_stats_db
            init_stats_db()
            summary = get_summary()
            today = get_today_summary()
        except Exception as e:
            ttk.Label(main, text=f"Error loading stats: {e}").pack()
            root.mainloop()
            return

        # --- Big numbers row ---
        big_frame = ttk.Frame(main)
        big_frame.pack(fill="x", pady=(0, 15))

        # Total words
        col1 = ttk.Frame(big_frame)
        col1.pack(side="left", expand=True)
        ttk.Label(col1, text=f"{summary['total_words']:,}", style="Big.TLabel").pack()
        ttk.Label(col1, text="words dictated", style="Unit.TLabel").pack()

        # Time saved
        time_saved = summary["time_saved_seconds"]
        if time_saved > 3600:
            time_str = f"{time_saved / 3600:.1f}"
            time_unit = "hours saved"
        elif time_saved > 60:
            time_str = f"{time_saved / 60:.0f}"
            time_unit = "minutes saved"
        else:
            time_str = f"{time_saved:.0f}"
            time_unit = "seconds saved"

        col2 = ttk.Frame(big_frame)
        col2.pack(side="left", expand=True)
        ttk.Label(col2, text=time_str, style="Big.TLabel").pack()
        ttk.Label(col2, text=time_unit, style="Unit.TLabel").pack()

        # Total transcriptions
        col3 = ttk.Frame(big_frame)
        col3.pack(side="left", expand=True)
        ttk.Label(col3, text=f"{summary['total_transcriptions']:,}", style="Big.TLabel").pack()
        ttk.Label(col3, text="transcriptions", style="Unit.TLabel").pack()

        # --- Today ---
        today_frame = tk.Frame(main, bg="#313244", padx=12, pady=8)
        today_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(today_frame, text="Today:", style="Stat.TLabel").pack(side="left", padx=(0, 15))
        ttk.Label(today_frame, text=f"{today['transcriptions']} transcriptions", style="Stat.TLabel").pack(side="left", padx=(0, 15))
        ttk.Label(today_frame, text=f"{today['words']} words", style="Stat.TLabel").pack(side="left", padx=(0, 15))
        ttk.Label(today_frame, text=f"{today['duration']:.0f}s recording", style="Stat.TLabel").pack(side="left")

        # --- Details ---
        detail_frame = ttk.Frame(main)
        detail_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(detail_frame, text=f"Voice commands used: {summary['total_commands']}").pack(anchor="w")

        if summary["busiest_hour"] is not None:
            h = summary["busiest_hour"]
            label = f"{h}:00" if h >= 10 else f"0{h}:00"
            ttk.Label(detail_frame, text=f"Most active hour: {label}").pack(anchor="w")

        ttk.Label(detail_frame, text=f"Avg words per transcription: {summary['total_words'] // max(1, summary['total_transcriptions'])}").pack(anchor="w")

        # --- Words by day (last 7 days) ---
        if summary["words_by_day"]:
            ttk.Label(main, text="LAST 7 DAYS", style="Header.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))

            chart_frame = tk.Frame(main, bg="#313244", padx=10, pady=10)
            chart_frame.pack(fill="x", pady=(0, 12))

            max_words = max(w for _, w in summary["words_by_day"]) if summary["words_by_day"] else 1
            bar_width = 50

            for date_str, words in summary["words_by_day"]:
                row = tk.Frame(chart_frame, bg="#313244")
                row.pack(fill="x", pady=1)

                day_label = date_str[5:]  # "MM-DD"
                ttk.Label(row, text=day_label, style="Stat.TLabel", width=6).pack(side="left")

                bar_len = int((words / max(1, max_words)) * 200)
                bar = tk.Frame(row, bg="#89b4fa", height=14, width=max(2, bar_len))
                bar.pack(side="left", padx=(5, 5))
                bar.pack_propagate(False)

                ttk.Label(row, text=f"{words}", style="Stat.TLabel").pack(side="left")

        # --- Top apps ---
        if summary["top_apps"]:
            ttk.Label(main, text="TOP APPS", style="Header.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))

            apps_frame = tk.Frame(main, bg="#313244", padx=10, pady=8)
            apps_frame.pack(fill="x", pady=(0, 12))

            for app_name, count, words in summary["top_apps"]:
                row = tk.Frame(apps_frame, bg="#313244")
                row.pack(fill="x", pady=1)
                short = app_name.replace(".exe", "")
                ttk.Label(row, text=f"{short}: {count} uses, {words} words", style="Stat.TLabel").pack(anchor="w")

        # --- Top commands ---
        if summary["top_commands"]:
            ttk.Label(main, text="TOP VOICE COMMANDS", style="Header.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))

            cmds_frame = tk.Frame(main, bg="#313244", padx=10, pady=8)
            cmds_frame.pack(fill="x", pady=(0, 12))

            for cmd_name, count in summary["top_commands"]:
                ttk.Label(cmds_frame, text=f"{cmd_name}: {count}x", style="Stat.TLabel").pack(anchor="w")

        # Close button
        ttk.Button(main, text="Close", command=root.destroy).pack(anchor="e", pady=(10, 0))

        root.mainloop()
