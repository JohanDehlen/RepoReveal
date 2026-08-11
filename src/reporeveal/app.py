from __future__ import annotations

import csv
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .github_client import GitHubSearchError, search_repositories
from .models import Repository
from .settings import load_window_geometry, save_window_geometry


class RepoRevealApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RepoReveal")
        self.geometry(load_window_geometry(default="1120x650"))
        self.minsize(900, 520)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.results: list[Repository] = []

        self.days_var = tk.StringVar(value="7")
        self.stars_var = tk.StringVar(value="10")
        self.language_var = tk.StringVar(value="")
        self.max_results_var = tk.StringVar(value="50")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(
            outer,
            text="RepoReveal",
            font=("Segoe UI", 20, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            outer,
            text="Discover promising names among recently created GitHub repositories.",
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))

        self._labeled_entry(controls, "Created within days", self.days_var, 0, 7)
        self._labeled_entry(controls, "Minimum stars", self.stars_var, 1, 7)
        self._labeled_entry(controls, "Language (optional)", self.language_var, 2, 16)
        self._labeled_entry(controls, "Max results", self.max_results_var, 3, 7)

        self.search_button = ttk.Button(
            controls,
            text="Search GitHub",
            command=self._start_search,
        )
        self.search_button.grid(row=1, column=4, padx=(12, 0), sticky="ew")

        self.export_button = ttk.Button(
            controls,
            text="Export CSV",
            command=self._export_csv,
            state="disabled",
        )
        self.export_button.grid(row=1, column=5, padx=(8, 0), sticky="ew")

        table = ttk.Frame(outer)
        table.pack(fill="both", expand=True)

        columns = ("name", "stars", "created", "language", "description")
        self.tree = ttk.Treeview(
            table,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("name", text="Repository")
        self.tree.heading("stars", text="Stars")
        self.tree.heading("created", text="Created")
        self.tree.heading("language", text="Language")
        self.tree.heading("description", text="Description")

        self.tree.column("name", width=210, anchor="w")
        self.tree.column("stars", width=75, anchor="e")
        self.tree.column("created", width=120, anchor="center")
        self.tree.column("language", width=110, anchor="w")
        self.tree.column("description", width=520, anchor="w")

        scrollbar = ttk.Scrollbar(
            table,
            orient="vertical",
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._open_selected)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))

        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Button(
            footer,
            text="Open selected repository",
            command=self._open_selected,
        ).pack(side="right")

    def _on_close(self) -> None:
        save_window_geometry(self.geometry())
        self.destroy()
    @staticmethod
    def _labeled_entry(
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        column: int,
        width: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(
            row=0,
            column=column,
            padx=(0, 8),
            sticky="w",
        )
        ttk.Entry(parent, textvariable=variable, width=width).grid(
            row=1,
            column=column,
            padx=(0, 8),
            sticky="ew",
        )

    def _start_search(self) -> None:
        try:
            days = int(self.days_var.get())
            stars = int(self.stars_var.get())
            max_results = int(self.max_results_var.get())
            if days < 1:
                raise ValueError
            if stars < 0:
                raise ValueError
            if not 1 <= max_results <= 100:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid search",
                "Use whole numbers: days >= 1, stars >= 0, and max results 1-100.",
            )
            return

        self.search_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.status_var.set("Searching GitHub...")

        thread = threading.Thread(
            target=self._search_worker,
            kwargs={
                "days": days,
                "min_stars": stars,
                "language": self.language_var.get(),
                "max_results": max_results,
            },
            daemon=True,
        )
        thread.start()

    def _search_worker(self, **kwargs: object) -> None:
        try:
            results = search_repositories(**kwargs)
        except (GitHubSearchError, ValueError) as exc:
            self.after(0, self._search_failed, str(exc))
            return
        self.after(0, self._search_complete, results)

    def _search_complete(self, results: list[Repository]) -> None:
        self.results = results

        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, repo in enumerate(results):
            created = repo.created_at[:10]
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    repo.full_name,
                    f"{repo.stars:,}",
                    created,
                    repo.language or "-",
                    repo.description,
                ),
            )

        self.search_button.configure(state="normal")
        self.export_button.configure(
            state="normal" if results else "disabled",
        )
        self.status_var.set(f"Found {len(results)} repositories.")

    def _search_failed(self, message: str) -> None:
        self.search_button.configure(state="normal")
        self.status_var.set("Search failed.")
        messagebox.showerror("GitHub search failed", message)

    def _selected_repository(self) -> Repository | None:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return self.results[int(selection[0])]
        except (IndexError, ValueError):
            return None

    def _open_selected(self, _event: object | None = None) -> None:
        repo = self._selected_repository()
        if repo and repo.html_url:
            webbrowser.open(repo.html_url)

    def _export_csv(self) -> None:
        if not self.results:
            return

        path = filedialog.asksaveasfilename(
            title="Export RepoReveal results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="reporeveal-results.csv",
        )
        if not path:
            return

        destination = Path(path)
        with destination.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "name",
                    "full_name",
                    "stars",
                    "created_at",
                    "language",
                    "description",
                    "github_url",
                ]
            )
            for repo in self.results:
                writer.writerow(
                    [
                        repo.name,
                        repo.full_name,
                        repo.stars,
                        repo.created_at,
                        repo.language,
                        repo.description,
                        repo.html_url,
                    ]
                )

        self.status_var.set(f"Exported {len(self.results)} rows to {destination.name}.")


def main() -> None:
    app = RepoRevealApp()
    app.mainloop()


if __name__ == "__main__":
    main()