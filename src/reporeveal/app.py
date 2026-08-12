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
from .scoring import score_repository
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
        self.category_var = tk.StringVar(value="")
        self.candidate_pool_var = tk.StringVar(value="100")
        self.domain_checks_var = tk.StringVar(value="20")
        self.final_results_var = tk.StringVar(value="10")
        self.domain_check_limit = 20
        self.final_result_limit = 10
        self.status_var = tk.StringVar(value="Ready.")
        self.score_explanation_var = tk.StringVar(value="")
        self.com_checked_rows: set[int] = set()

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
        self._labeled_entry(controls, "Language (optional)", self.language_var, 2, 11)
        self._labeled_entry(controls, "Category (optional)", self.category_var, 3, 14)
        self._labeled_entry(
            controls,
            "Candidate pool",
            self.candidate_pool_var,
            4,
            7,
        )
        self._labeled_entry(
            controls,
            "Live domain checks",
            self.domain_checks_var,
            5,
            7,
        )
        self._labeled_entry(
            controls,
            "Final results",
            self.final_results_var,
            6,
            7,
        )

        self.search_button = ttk.Button(
            controls,
            text="Search GitHub",
            command=self._start_search,
        )
        self.search_button.grid(row=1, column=7, padx=(12, 0), sticky="ew")

        self.export_button = ttk.Button(
            controls,
            text="Export CSV",
            command=self._export_csv,
            state="disabled",
        )
        self.export_button.grid(row=1, column=8, padx=(8, 0), sticky="ew")

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
            "score",
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
        self.tree.heading("score", text="Score")
        self.tree.heading("name", text="Repository")
        self.tree.heading("stars", text="Stars")
        self.tree.heading("created", text="Created")
        self.tree.heading("language", text="Language")
        self.tree.heading("search_term", text="Search term")
        for tld in SUPPORTED_TLDS:
            self.tree.heading(tld, text=f".{tld}")
        self.tree.heading("description", text="Description")

        self.tree.column("score", width=55, minwidth=50, anchor="center", stretch=False)
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
        self.tree.bind("<<TreeviewSelect>>", self._update_score_explanation)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))

        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Label(
            footer,
            textvariable=self.score_explanation_var,
        ).pack(side="left", padx=(18, 0))
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
            candidate_pool = int(self.candidate_pool_var.get())
            domain_checks = int(self.domain_checks_var.get())
            final_results = int(self.final_results_var.get())

            if days < 1:
                raise ValueError
            if stars < 0:
                raise ValueError
            if not 1 <= candidate_pool <= 300:
                raise ValueError
            if not 0 <= domain_checks <= candidate_pool:
                raise ValueError
            if not 1 <= final_results <= candidate_pool:
                raise ValueError
            if domain_checks and final_results > domain_checks:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid search",
                "Use whole numbers: days >= 1, stars >= 0, "
                "candidate pool 1-300, live domain checks 0-candidate pool, "
                "and final results 1-candidate pool. When live checks are "
                "enabled, final results cannot exceed live domain checks.",
            )
            return

        self.domain_check_limit = domain_checks
        self.final_result_limit = final_results

        self.domain_check_generation += 1
        self.com_checked_rows.clear()
        self.search_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.status_var.set("Searching GitHub...")

        thread = threading.Thread(
            target=self._search_worker,
            kwargs={
                "days": days,
                "min_stars": stars,
                "language": self.language_var.get(),
                "category": self.category_var.get(),
                "max_results": candidate_pool,
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
            initial_score = score_repository(
                repo,
                search_term,
                com_available=False,
            ).candidate_score
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    initial_score,
                    repo.full_name,
                    f"{repo.stars:,}",
                    created,
                    repo.language or "-",
                    search_term or "-",
                    *("" for _ in SUPPORTED_TLDS),
                    repo.description,
                ),
            )

        self._sort_by_score()

        preliminary_limit = (
            self.domain_check_limit
            if self.domain_check_limit
            else self.final_result_limit
        )
        self._limit_visible_rows(preliminary_limit)
        self._autofit_columns()

        self.search_button.configure(state="normal")
        self.export_button.configure(
            state="normal" if results else "disabled",
        )

        if results:
            finalist_count = min(len(results), self.domain_check_limit)
            if finalist_count:
                self.status_var.set(
                    f"Scored {len(results)} candidates. "
                    f"Checking domains for top {finalist_count}..."
                )
                self._start_domain_checks(results)
            else:
                self.status_var.set(
                    f"Scored {len(results)} candidates. "
                    f"Showing top {min(len(results), self.final_result_limit)} "
                    "candidates; live domain checks disabled."
                )
        else:
            self.status_var.set("Found 0 repositories.")

    def _limit_visible_rows(self, limit: int) -> None:
        items = list(self.tree.get_children())
        for iid in items[limit:]:
            self.tree.delete(iid)

    def _autofit_columns(self) -> None:
        tree_font = tkfont.nametofont("TkDefaultFont")
        heading_font = tkfont.nametofont("TkHeadingFont")

        # Keep data columns only as wide as needed, with caps on fields that can
        # contain unusually long names. Description is intentionally excluded
        # and stretches to consume the remaining window width.
        caps = {
            "score": 65,
            "name": 260,
            "stars": 80,
            "created": 105,
            "language": 120,
            "search_term": 230,
        }
        padding = {
            "score": 14,
            "name": 18,
            "stars": 16,
            "created": 16,
            "language": 18,
            "search_term": 18,
        }

        for column in ("score", "name", "stars", "created", "language", "search_term"):
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

        finalist_iids = list(self.tree.get_children())[: self.domain_check_limit]
        finalist_rows = [(int(iid), results[int(iid)]) for iid in finalist_iids]

        with ThreadPoolExecutor(max_workers=4) as executor:
            for row_index, repo in finalist_rows:
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

        if tld == "com" and 0 <= row_index < len(self.results):
            self.com_checked_rows.add(row_index)

            repo = self.results[row_index]
            search_term = normalize_repo_name(repo.name)
            score = score_repository(
                repo,
                search_term,
                com_available=result.status is DomainStatus.AVAILABLE,
            ).total
            self.tree.set(iid, "score", score)

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
        self._sort_by_score()
        self._limit_visible_rows(self.final_result_limit)

        visible = len(self.tree.get_children())
        checked = min(len(self.results), self.domain_check_limit)
        self.status_var.set(
            f"Scored {len(self.results)} candidates. "
            f"Checked top {checked}; showing {visible} final opportunities "
            f"({checked_count} domain checks)."
        )

    def _sort_by_score(self) -> None:
        items = list(self.tree.get_children())
        items.sort(
            key=lambda iid: int(self.tree.set(iid, "score") or 0),
            reverse=True,
        )
        for position, iid in enumerate(items):
            self.tree.move(iid, "", position)

    def _search_failed(self, message: str) -> None:
        self.search_button.configure(state="normal")
        self.status_var.set("Search failed.")
        messagebox.showerror("GitHub search failed", message)

    def _update_score_explanation(self, _event: object | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            self.score_explanation_var.set("")
            return

        iid = selection[0]
        try:
            row_index = int(iid)
            repo = self.results[row_index]
        except (IndexError, ValueError):
            self.score_explanation_var.set("")
            return

        search_term = normalize_repo_name(repo.name)
        com_checked = row_index in self.com_checked_rows
        com_available = (
            com_checked
            and self.tree.set(iid, "com") == "✓"
        )

        breakdown = score_repository(
            repo,
            search_term,
            com_available=com_available,
        )

        components = (
            f"Candidate {breakdown.candidate_score}/75 = "
            f"Name {breakdown.name_quality}/30 + "
            f"Brand {breakdown.brandability}/20 + "
            f"Momentum {breakdown.momentum}/25 - "
            f"Penalties {breakdown.penalties}"
        )

        if com_checked:
            self.score_explanation_var.set(
                f"{components}    |    "
                f"Opportunity {breakdown.total}/100 "
                f"(domain bonus +{breakdown.com_bonus})"
            )
        else:
            self.score_explanation_var.set(
                f"{components}    |    Opportunity not evaluated"
            )

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
                    "score",
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

            visible_iids = list(self.tree.get_children())
            for iid in visible_iids:
                index = int(iid)
                repo = self.results[index]
                domain_values = [
                    self.tree.set(iid, tld)
                    for tld in SUPPORTED_TLDS
                ]
                writer.writerow(
                    [
                        self.tree.set(iid, "score"),
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
            f"Exported {len(visible_iids)} rows to {destination.name}."
        )


def main() -> None:
    app = RepoRevealApp()
    app.mainloop()


if __name__ == "__main__":
    main()
