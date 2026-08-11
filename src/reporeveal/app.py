from __future__ import annotations

import csv
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from .domain_checker import (
    DomainResult,
    DomainStatus,
    SUPPORTED_TLDS,
    check_domain_rdap,
    normalize_repo_name,
)
from .github_client import GitHubSearchError, search_repositories
from .models import Repository
from .settings import load_window_geometry, save_window_geometry


class RepoRevealApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RepoReveal")
        self._saved_window_geometry = load_window_geometry(default="1120x650")
        self.geometry("1120x650")
        self.minsize(900, 520)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.results: list[Repository] = []
        self.domain_cache: dict[str, DomainResult] = {}
        self.domain_check_generation = 0

        self.days_var = tk.StringVar(value="7")
        self.stars_var = tk.StringVar(value="10")
        self.language_var = tk.StringVar(value="")
        self.max_results_var = tk.StringVar(value="50")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self.after_idle(self._restore_window_geometry)

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

        legend = ttk.Frame(outer)
        legend.pack(fill="x", pady=(0, 4))

        ttk.Label(
            legend,
            text="✓ - Available",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(820, 0))

        table = ttk.Frame(outer)
        table.pack(fill="both", expand=True)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        columns = (
            "name",
            "stars",
            "created",
            "language",
            "search_term",
            *SUPPORTED_TLDS,
            "description",
        )
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
        self.tree.heading("search_term", text="Search term")
        for tld in SUPPORTED_TLDS:
            self.tree.heading(tld, text=f".{tld}")
        self.tree.heading("description", text="Description")

        self.tree.column("name", width=140, minwidth=80, anchor="w", stretch=False)
        self.tree.column("stars", width=55, minwidth=45, anchor="e", stretch=False)
        self.tree.column("created", width=85, minwidth=75, anchor="center", stretch=False)
        self.tree.column("language", width=70, minwidth=55, anchor="w", stretch=False)
        self.tree.column("search_term", width=110, minwidth=80, anchor="w", stretch=False)
        for tld in SUPPORTED_TLDS:
            self.tree.column(tld, width=42, minwidth=38, anchor="center", stretch=False)
        self.tree.column("description", width=220, minwidth=180, anchor="w", stretch=True)

        y_scrollbar = ttk.Scrollbar(
            table,
            orient="vertical",
            command=self.tree.yview,
        )
        x_scrollbar = ttk.Scrollbar(
            table,
            orient="horizontal",
            command=self.tree.xview,
        )
        self.tree.configure(
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<Double-1>", self._open_selected)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))

        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Button(
            footer,
            text="Open selected repository",
            command=self._open_selected,
        ).pack(side="right")

    def _restore_window_geometry(self) -> None:
        self.update_idletasks()
        self.geometry(self._saved_window_geometry)

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

        self.domain_check_generation += 1
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
            search_term = normalize_repo_name(repo.name)
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    repo.full_name,
                    f"{repo.stars:,}",
                    created,
                    repo.language or "-",
                    search_term or "-",
                    *("…" for _ in SUPPORTED_TLDS),
                    repo.description,
                ),
            )

        self._autofit_columns()

        self.search_button.configure(state="normal")
        self.export_button.configure(
            state="normal" if results else "disabled",
        )

        if results:
            self.status_var.set(
                f"Found {len(results)} repositories. Checking domains..."
            )
            self._start_domain_checks(results)
        else:
            self.status_var.set("Found 0 repositories.")

    def _autofit_columns(self) -> None:
        tree_font = tkfont.nametofont("TkDefaultFont")
        heading_font = tkfont.nametofont("TkHeadingFont")

        # Keep data columns only as wide as needed, with caps on fields that can
        # contain unusually long names. Description is intentionally excluded
        # and stretches to consume the remaining window width.
        caps = {
            "name": 260,
            "stars": 80,
            "created": 105,
            "language": 120,
            "search_term": 230,
        }
        padding = {
            "name": 18,
            "stars": 16,
            "created": 16,
            "language": 18,
            "search_term": 18,
        }

        for column in ("name", "stars", "created", "language", "search_term"):
            heading = self.tree.heading(column, "text")
            width = heading_font.measure(heading) + padding[column]

            for iid in self.tree.get_children():
                value = str(self.tree.set(iid, column))
                width = max(width, tree_font.measure(value) + padding[column])

            self.tree.column(
                column,
                width=min(width, caps[column]),
                stretch=False,
            )

        for tld in SUPPORTED_TLDS:
            heading_width = heading_font.measure(f".{tld}") + 14
            self.tree.column(
                tld,
                width=max(38, heading_width),
                stretch=False,
            )

    def _start_domain_checks(self, results: list[Repository]) -> None:
        self.domain_check_generation += 1
        generation = self.domain_check_generation

        thread = threading.Thread(
            target=self._domain_check_worker,
            args=(generation, results),
            daemon=True,
        )
        thread.start()

    def _domain_check_worker(
        self,
        generation: int,
        results: list[Repository],
    ) -> None:
        jobs: dict[Future[DomainResult], tuple[int, str]] = {}
        cached_count = 0

        with ThreadPoolExecutor(max_workers=4) as executor:
            for row_index, repo in enumerate(results):
                label = normalize_repo_name(repo.name)
                if not label:
                    continue

                for tld in SUPPORTED_TLDS:
                    domain = f"{label}.{tld}"
                    cached = self.domain_cache.get(domain)
                    if cached is not None:
                        cached_count += 1
                        self.after(
                            0,
                            self._update_domain_cell,
                            generation,
                            row_index,
                            tld,
                            cached,
                        )
                        continue

                    future = executor.submit(check_domain_rdap, domain)
                    jobs[future] = (row_index, tld)

            completed = 0
            total = len(jobs)

            if total == 0:
                self.after(0, self._domain_checks_complete, generation, cached_count)
                return

            for future in as_completed(jobs):
                row_index, tld = jobs[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = DomainResult(
                        "",
                        DomainStatus.UNKNOWN,
                        type(exc).__name__,
                    )

                if result.domain:
                    self.domain_cache[result.domain] = result

                completed += 1
                self.after(
                    0,
                    self._update_domain_cell,
                    generation,
                    row_index,
                    tld,
                    result,
                )
                if completed % 5 == 0 or completed == total:
                    self.after(
                        0,
                        self._update_domain_progress,
                        generation,
                        completed,
                        total,
                        cached_count,
                    )

        self.after(
            0,
            self._domain_checks_complete,
            generation,
            cached_count + total,
        )

    def _update_domain_cell(
        self,
        generation: int,
        row_index: int,
        tld: str,
        result: DomainResult,
    ) -> None:
        if generation != self.domain_check_generation:
            return

        iid = str(row_index)
        if not self.tree.exists(iid):
            return

        symbol = "✓" if result.status is DomainStatus.AVAILABLE else ""
        self.tree.set(iid, tld, symbol)

    def _update_domain_progress(
        self,
        generation: int,
        completed: int,
        total: int,
        cached_count: int,
    ) -> None:
        if generation != self.domain_check_generation:
            return

        overall_completed = cached_count + completed
        overall_total = cached_count + total
        self.status_var.set(
            f"Found {len(self.results)} repositories. "
            f"Domain checks: {overall_completed}/{overall_total}"
        )

    def _domain_checks_complete(
        self,
        generation: int,
        checked_count: int,
    ) -> None:
        if generation != self.domain_check_generation:
            return
        self.status_var.set(
            f"Found {len(self.results)} repositories. "
            f"Domain checks complete ({checked_count})."
        )

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
                    "search_term",
                    *SUPPORTED_TLDS,
                    "description",
                    "github_url",
                ]
            )

            for index, repo in enumerate(self.results):
                iid = str(index)
                domain_values = [
                    self.tree.set(iid, tld) if self.tree.exists(iid) else ""
                    for tld in SUPPORTED_TLDS
                ]
                writer.writerow(
                    [
                        repo.name,
                        repo.full_name,
                        repo.stars,
                        repo.created_at,
                        repo.language,
                        normalize_repo_name(repo.name),
                        *domain_values,
                        repo.description,
                        repo.html_url,
                    ]
                )

        self.status_var.set(
            f"Exported {len(self.results)} rows to {destination.name}."
        )


def main() -> None:
    app = RepoRevealApp()
    app.mainloop()


if __name__ == "__main__":
    main()