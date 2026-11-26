# SPDX-License-Identifier: AGPL-3.0-or-later
"""LUPA desktop interface with threaded computation and queued progress updates."""

from dataclasses import replace
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import load_config
from .pipeline import run_pipeline


METRIC_LABELS = (
    ("equivalent", "Equivalent diameter / SSA"),
    ("wadell", "Sphericity"),
    ("pca", "PCA axis ratios"),
    ("shape", "Radial variance"),
    ("roughness", "Roughness"),
    ("fractal", "Repaired mesh fractal"),
    ("filter_fractal", "Simplified mesh fractal"),
)
RESULT_COLUMNS = ("name", "d_v", "Wadell", "EI", "Ra", "Rz", "D_repair")
RESULT_LABELS = ("Particle", "Diameter", "Sphericity", "Elongation EI", "Mean distance Ra", "Std. dev. Rz", "Fractal D (repair)")


class AnalysisWindow:
    """Configuration, batch analysis, and result browsing in one window."""

    def __init__(self, root, config_path):
        self.root = root
        root.title("LUPA V1.0 - Lunar Regolith Particle Analyzer")
        root.geometry("1160x820")
        root.minsize(1000, 740)
        root.report_callback_exception = self._callback_error
        self.queue = Queue()
        self.records = {}
        self.run_settings = None
        self.config_path = tk.StringVar(value=str(Path(config_path).resolve()))
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.fraction = tk.StringVar()
        self.tag = tk.StringVar()
        self.workers = tk.StringVar()
        self.voxel = tk.StringVar()
        self.metric_vars = {key: tk.BooleanVar() for key, _ in METRIC_LABELS}
        self.status = tk.StringVar(value="Ready")
        self.progress_value = tk.DoubleVar(value=0)
        self._build_interface()
        self._load_config()
        root.after(100, self._poll_queue)

    def _build_interface(self):
        style = ttk.Style(self.root)
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(9, 5))
        style.configure("TCheckbutton", font=("Segoe UI", 9))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(
            main, text="Lunar Regolith Particle Analyzer",
            font=("Segoe UI", 19, "bold"), foreground="#203d59",
        ).pack(anchor="w")
        ttk.Label(
            main, text="LUPA  V1.0    STL preprocessing | Morphology | Surface texture | Batch analysis",
            foreground="#526578",
        ).pack(anchor="w", pady=(4, 12))

        config_bar = ttk.Frame(main)
        config_bar.pack(fill="x", pady=(0, 10))
        ttk.Label(config_bar, text="Config file", width=12).pack(side="left")
        ttk.Entry(config_bar, textvariable=self.config_path).pack(side="left", fill="x", expand=True)
        ttk.Button(config_bar, text="Choose file", command=self._choose_config).pack(side="left", padx=(8, 4))
        ttk.Button(config_bar, text="Load config", command=self._load_config).pack(side="left")

        paths = ttk.LabelFrame(main, text="Input and output", padding=(12, 8))
        paths.pack(fill="x", pady=(0, 10))
        paths.columnconfigure(1, weight=1)
        self._directory_row(paths, 0, "STL input folder", self.input_path)
        self._directory_row(paths, 1, "Output folder", self.output_path)

        parameters = ttk.LabelFrame(main, text="Analysis parameters", padding=(12, 9))
        parameters.pack(fill="x", pady=(0, 10))
        parameter_fields = (
            ("Face retention", self.fraction, 10),
            ("Result tag", self.tag, 10),
            ("Workers", self.workers, 6),
            ("Voxel size (mm)", self.voxel, 10),
        )
        for column, (label, variable, width) in enumerate(parameter_fields):
            ttk.Label(parameters, text=label).grid(row=0, column=2 * column, padx=(0, 7), sticky="w")
            ttk.Entry(parameters, textvariable=variable, width=width).grid(
                row=0, column=2 * column + 1, padx=(0, 16), sticky="w"
            )
        ttk.Label(
            parameters, text="Face retention: (0, 1]. Voxel size accepts auto. Rz is the sample standard deviation of surface distances.",
            foreground="#526578", font=("Segoe UI", 9),
        ).grid(row=1, column=0, columnspan=8, sticky="w", pady=(8, 0))

        metrics = ttk.LabelFrame(main, text="Metrics", padding=(12, 8))
        metrics.pack(fill="x", pady=(0, 12))
        for index, (key, label) in enumerate(METRIC_LABELS):
            ttk.Checkbutton(metrics, text=label, variable=self.metric_vars[key]).grid(
                row=index // 4, column=index % 4, sticky="w", padx=(0, 20), pady=3
            )

        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(0, 8))
        self.start_button = ttk.Button(actions, text="Start analysis", command=self._start)
        self.start_button.pack(side="left")
        self.preview_button = ttk.Button(actions, text="Preview particle", command=self._preview, state="disabled")
        self.preview_button.pack(side="left", padx=8)
        self.folder_button = ttk.Button(actions, text="Open results", command=self._open_results, state="disabled")
        self.folder_button.pack(side="left")
        ttk.Progressbar(actions, variable=self.progress_value, maximum=100).pack(
            side="left", fill="x", expand=True, padx=(18, 10)
        )
        ttk.Label(main, textvariable=self.status, foreground="#203d59").pack(anchor="w", pady=(0, 8))

        panes = ttk.Panedwindow(main, orient="vertical")
        panes.pack(fill="both", expand=True)
        result_frame = ttk.LabelFrame(panes, text="Results", padding=4)
        self.table = ttk.Treeview(result_frame, columns=RESULT_COLUMNS, show="headings", height=8)
        for key, label in zip(RESULT_COLUMNS, RESULT_LABELS):
            self.table.heading(key, text=label)
            self.table.column(key, width=240 if key == "name" else 120, minwidth=90, anchor="w" if key == "name" else "e")
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.table.bind("<Double-1>", lambda event: self._preview())
        panes.add(result_frame, weight=3)
        log_frame = ttk.LabelFrame(panes, text="Run log", padding=4)
        self.log = tk.Text(log_frame, height=7, wrap="word", state="disabled", font=("Segoe UI", 9))
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        panes.add(log_frame, weight=1)

    def _directory_row(self, parent, row, label, variable):
        ttk.Label(parent, text=label, width=16).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(
            parent, text="Browse", command=lambda: self._choose_directory(variable)
        ).grid(row=row, column=2, padx=(8, 0), pady=4)

    def _choose_directory(self, variable):
        chosen = filedialog.askdirectory(parent=self.root, title="Select folder", initialdir=variable.get())
        if chosen:
            variable.set(chosen)

    def _choose_config(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="Select configuration file",
                                              filetypes=[("Configuration files", "*.ini"), ("All files", "*.*")])
        if chosen:
            self.config_path.set(chosen)
            self._load_config()

    def _load_config(self):
        self.settings = load_config(Path(self.config_path.get()))
        self.input_path.set(str(self.settings.input_dir))
        self.output_path.set(str(self.settings.result_dir.parent))
        self.fraction.set(str(self.settings.fraction))
        self.tag.set(self.settings.tag)
        self.workers.set(str(self.settings.workers))
        self.voxel.set("auto" if self.settings.voxel_size is None else str(self.settings.voxel_size))
        for key, variable in self.metric_vars.items():
            variable.set(key in self.settings.metrics)
        self._append_log(f"Loaded configuration: {self.config_path.get()}")

    def _settings_for_run(self):
        output = Path(self.output_path.get()).expanduser().resolve()
        voxel_text = self.voxel.get().strip()
        return replace(
            self.settings,
            input_dir=Path(self.input_path.get()).expanduser().resolve(),
            repaired_dir=output / "stl" / "repaired",
            filtered_dir=output / "stl" / "filtered",
            repair_mesh_dir=output / "meshes" / "repaired",
            filter_mesh_dir=output / "meshes" / "filtered",
            result_dir=output / "results",
            repair_image_dir=output / "images" / "repaired",
            filter_image_dir=output / "images" / "filtered",
            fraction=float(self.fraction.get()), tag=self.tag.get().strip(),
            workers=int(self.workers.get()),
            voxel_size=None if voxel_text.lower() == "auto" else float(voxel_text),
            export="png",
            metrics=tuple(key for key, variable in self.metric_vars.items() if variable.get()),
        )

    def _start(self):
        self.run_settings = self._settings_for_run()
        self.start_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.folder_button.configure(state="disabled")
        self.table.delete(*self.table.get_children())
        self.records.clear()
        self.progress_value.set(0)
        self.status.set("Processing particles...")
        self._append_log(f"Input folder: {self.run_settings.input_dir}")
        self._append_log(f"Output folder: {self.run_settings.result_dir.parent}")
        Thread(target=self._calculate, args=(self.run_settings,), daemon=True).start()

    def _calculate(self, settings):
        def progress(done, total, name):
            self.queue.put(("progress", (done, total, name)))

        try:
            result = run_pipeline(settings, progress=progress, stage="all")
            self.queue.put(("complete", result))
        except Exception as error:
            self.queue.put(("error", error))

    def _poll_queue(self):
        while True:
            try:
                event, value = self.queue.get_nowait()
            except Empty:
                break
            if event == "progress":
                done, total, name = value
                self.progress_value.set(100 * done / total if total else 0)
                self.status.set(f"Processed {done} / {total} particles    {name}")
                self._append_log(f"[{done}/{total}] {name}")
            elif event == "complete":
                self._show_result(value)
            elif event == "error":
                self.start_button.configure(state="normal")
                self.status.set("Analysis failed")
                self._append_log(f"Analysis failed: {value}")
                messagebox.showerror("Analysis failed", str(value), parent=self.root)
        self.root.after(100, self._poll_queue)

    def _show_result(self, result):
        for index, row in enumerate(result.rows):
            row_id = str(index)
            self.records[row_id] = row
            cells = [row["name"]]
            groups = ("equivalent", "wadell", "pca", "roughness", "roughness", "fractal")
            cells.extend(
                f"{row[key]:.6g}" if group in self.run_settings.metrics else "--"
                for key, group in zip(RESULT_COLUMNS[1:], groups)
            )
            self.table.insert("", "end", iid=row_id, values=cells)
        if result.rows:
            self.table.selection_set("0")
            self.preview_button.configure(state="normal")
        self.folder_button.configure(state="normal")
        self.start_button.configure(state="normal")
        self.progress_value.set(100)
        self.status.set(f"Analysis complete: {len(result.rows)} particles. Full metrics are in the results folder.")
        self._append_log(f"Results: {result.csv_path}")
        self._append_log(f"Run metadata: {result.json_path}")

    def _preview(self):
        selected = self.table.selection()
        if not selected:
            return
        name = Path(self.records[selected[0]]["name"]).stem
        picture = self.run_settings.repair_image_dir / f"{name}.png"
        os.startfile(str(picture))

    def _open_results(self):
        os.startfile(str(self.run_settings.result_dir))

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _callback_error(self, exception_type, error, traceback):
        self._append_log(f"Operation failed: {error}")
        messagebox.showerror("Operation failed", str(error), parent=self.root)


def run(config_path):
    root = tk.Tk()
    AnalysisWindow(root, config_path)
    root.mainloop()
