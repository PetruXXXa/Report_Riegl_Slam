"""
Модуль с графическим интерфейсом пользователя.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import os
import webbrowser
import tempfile

from data_models import ProjectData, ReportData
from data_extractor import DataExtractor
from statistics_calculator import StatisticsCalculator
from map_builder import MapBuilder
from graph_builder import GraphBuilder
from report_filler import ReportFiller
from exporters import ReportExporter


class HTMLPreviewFrame(tk.Frame):
    """
    Фрейм для предпросмотра HTML с поддержкой навигации
    """

    def __init__(self, parent, main_gui=None, **kwargs):
        super().__init__(parent, **kwargs)

        # Данные
        self.html_content = None
        self.temp_html_path = None
        self.filler = None
        self.main_gui = main_gui  # Ссылка на главный GUI
        self.preview_frame = None

        # Создаем тулбар
        self.toolbar = tk.Frame(self, bg="#f0f0f0", height=30)
        self.toolbar.pack(fill=tk.X)
        self.toolbar.pack_propagate(False)

        # Кнопки
        self.open_btn = tk.Button(
            self.toolbar,
            text="Открыть в браузере",
            command=self.open_in_browser,
            state=tk.DISABLED,
        )
        self.open_btn.pack(side=tk.LEFT, padx=5, pady=2)

        self.refresh_btn = tk.Button(
            self.toolbar,
            text="Обновить",
            command=self.refresh_preview,
            state=tk.DISABLED,
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=5, pady=2)

        # Статус
        self.status_label = tk.Label(self.toolbar, text="", bg="#f0f0f0")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Контейнер для предпросмотра
        self.preview_container = tk.Frame(self)
        self.preview_container.pack(fill=tk.BOTH, expand=True)

    def set_filler(self, filler: ReportFiller):
        """Устанавливает ссылку на ReportFiller"""
        self.filler = filler

    def show_html(self, html_content: str):
        """
        Показывает HTML в предпросмотре
        """
        self.html_content = html_content

        # Очищаем предыдущий контент
        for widget in self.preview_container.winfo_children():
            widget.destroy()

        # Создаем новый предпросмотр через ReportFiller
        if self.filler:
            self.preview_frame, temp_path = self.filler.create_preview_widget(
                self.preview_container, html_content
            )
            # Обновляем путь к временному файлу
            if temp_path:
                self.temp_html_path = temp_path

        # Активируем кнопки
        self.open_btn.config(state=tk.NORMAL)
        self.refresh_btn.config(state=tk.NORMAL)

        self.status_label.config(text="✓ Отчет готов")

    def open_in_browser(self):
        """Открывает HTML во внешнем браузере"""
        if self.temp_html_path and os.path.exists(self.temp_html_path):
            webbrowser.open("file://" + self.temp_html_path)
            self.status_label.config(text="✓ Открыто в браузере")

    def save_html(self):
        """Сохраняет HTML в файл"""
        if not self.html_content:
            return

        from tkinter import filedialog

        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            title="Сохранить HTML отчет",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.html_content)
                self.status_label.config(
                    text=f"✓ Сохранено: {os.path.basename(file_path)}"
                )

                # Спрашиваем, открыть ли в браузере
                if messagebox.askyesno(
                    "Открыть отчет", "Открыть сохраненный отчет в браузере?"
                ):
                    webbrowser.open("file://" + file_path)

            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def refresh_preview(self):
        """Обновляет предпросмотр"""
        # Вызываем метод обновления из главного GUI
        if self.main_gui and hasattr(
            self.main_gui, "regenerate_report_with_current_settings"
        ):
            self.main_gui.regenerate_report_with_current_settings()
        elif self.html_content:
            # Если главный GUI недоступен, просто обновляем текущий HTML
            self.show_html(self.html_content)
            self.status_label.config(text="✓ Предпросмотр обновлен")

    def clear(self):
        """Очищает предпросмотр"""
        # Очищаем контейнер предпросмотра
        for widget in self.preview_container.winfo_children():
            widget.destroy()

        self.open_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)

        self.html_content = None
        self.status_label.config(text="")


class MSAReportGUI:
    """Главное окно программы"""

    def __init__(self, root):
        self.root = root
        self.root.title("Генератор отчетов НЛС. Для УГП №1. Версия 1.0")
        self.root.geometry("1400x800")

        # Модели данных
        self.report_data = ReportData()
        self.current_project = None

        # Компоненты
        self.extractor = DataExtractor()
        self.stat_calc = StatisticsCalculator()
        self.map_builder = MapBuilder()
        self.graph_builder = GraphBuilder()
        self.filler = ReportFiller()
        self.exporter = ReportExporter()

        # Переменные
        self.msa_directory = ""
        self.msa_projects = []
        self.rs10_projects = []
        self.project_vars = {}

        # Очередь для потоков
        self.update_queue = queue.Queue()

        # Флаги
        self.use_osm_maps = tk.BooleanVar(value=False)
        self.use_html_tables = tk.BooleanVar(value=True)

        # Текущий HTML для предпросмотра
        self.current_html_content = None

        # Для обработки диалогов HTML структуры
        self.last_html_structure_choice = None

        # Создаем интерфейс
        self.create_widgets()

        # Запускаем проверку очереди
        self.check_update_queue()

        # Обработчик закрытия
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """Создает элементы интерфейса"""
        # Основной фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Левая панель
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.config(width=350)

        # Правая панель (предпросмотр)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Кнопки управления
        self.create_control_panel(left_frame)

        # Фрейм выбора типа проектов
        self.create_type_selector(left_frame)

        # Фрейм со списком проектов
        self.create_project_list(left_frame)

        # Фрейм предпросмотра
        self.create_preview_area(right_frame)

        # Статус бар
        self.create_status_bar()

    def create_control_panel(self, parent):
        """Создает панель управления"""
        frame = ttk.LabelFrame(parent, text="Управление", padding=(5, 5))
        frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            frame, text="Выбрать директорию", command=self.select_directory
        ).pack(fill=tk.X, pady=2)

        ttk.Button(frame, text="Сохранить HTML", command=self.save_html_report).pack(
            fill=tk.X, pady=2
        )

        ttk.Button(frame, text="Экспорт в PDF", command=self.export_to_pdf).pack(
            fill=tk.X, pady=2
        )

        ttk.Button(frame, text="Экспорт в Word", command=self.export_to_word).pack(
            fill=tk.X, pady=2
        )

        ttk.Button(frame, text="Экспорт в JPEG", command=self.export_to_jpeg).pack(
            fill=tk.X, pady=2
        )

        ttk.Checkbutton(
            frame, text="Карты OSM (нужен интернет)", variable=self.use_osm_maps
        ).pack(fill=tk.X, pady=2)

    def create_type_selector(self, parent):
        """Создает переключатель типа проектов"""
        frame = ttk.LabelFrame(parent, text="Тип проектов", padding=(5, 5))
        frame.pack(fill=tk.X, pady=(0, 10))

        self.project_type_var = tk.StringVar(value="msa")
        self.project_type_var.trace("w", self.on_type_change)

        ttk.Radiobutton(
            frame, text="Riegl (MSA)", variable=self.project_type_var, value="msa"
        ).pack(anchor=tk.W, pady=2)

        ttk.Radiobutton(
            frame, text="RS10", variable=self.project_type_var, value="rs10"
        ).pack(anchor=tk.W, pady=2)

    def create_project_list(self, parent):
        """Создает список проектов"""
        self.projects_frame = ttk.LabelFrame(parent, text="Проекты", padding=(5, 5))
        self.projects_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas для скроллинга
        canvas = tk.Canvas(self.projects_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self.projects_frame, orient="vertical", command=canvas.yview
        )
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Кнопки выбора
        select_frame = ttk.Frame(self.projects_frame)
        select_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(select_frame, text="Выбрать все", command=self.select_all).pack(
            side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X
        )
        ttk.Button(select_frame, text="Снять все", command=self.deselect_all).pack(
            side=tk.LEFT, expand=True, fill=tk.X
        )

    def create_preview_area(self, parent):
        """Создает область предпросмотра"""
        preview_container = ttk.LabelFrame(
            parent, text="Предпросмотр отчета", padding=(5, 5)
        )
        preview_container.pack(fill=tk.BOTH, expand=True)

        # Создаем кастомный фрейм предпросмотра
        self.preview_frame = HTMLPreviewFrame(preview_container, main_gui=self)
        self.preview_frame.set_filler(self.filler)
        self.preview_frame.pack(fill=tk.BOTH, expand=True)

        # Показываем начальное сообщение
        self.show_initial_preview()

    def create_status_bar(self):
        """Создает строку состояния"""
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def show_initial_preview(self):
        """Показывает начальное сообщение"""
        initial_text = "=" * 60 + "\n"
        initial_text += "     ГЕНЕРАТОР ОТЧЕТОВ НЛС.\n"
        initial_text += "=" * 60 + "\n\n"
        initial_text += "Программа предназначена строго для работы внутри УГП №1.\n"
        initial_text += "=" * 60 + "\n\n"
        initial_text += "Для начала работы:\n"
        initial_text += "1. Нажмите 'Выбрать директорию'\n"
        initial_text += "2. Выберите папку с проектами\n"
        initial_text += "3. Отметьте нужные проекты в списке\n"
        initial_text += "4. Отчет появится автоматически\n\n"
        initial_text += "=" * 60 + "\n\n"
        initial_text += "ТРЕБОВАНИЯ К СТРУКТУРЕ ПАПОК:\n\n"
        initial_text += "Для Riegl (MSA):\n"
        initial_text += "  Папка проекта должна называться MSA2-*-log\n"
        initial_text += "  Внутри: control_points.csv, report.html, msa_sop.csv\n\n"
        initial_text += "Для RS10:\n"
        initial_text += "  Папка проекта должна содержать подпапку AUTOSOLVE/\n"
        initial_text += "  Внутри AUTOSOLVE:\n"
        initial_text += "    Scanner1/slam_trajectory.txt\n"
        initial_text += "    TGCPReport/SLAM_Refine_Report.csv\n\n"
        initial_text += "=" * 60

        # Создаем простой текстовый виджет для начального сообщения
        for widget in self.preview_frame.preview_container.winfo_children():
            widget.destroy()

        text_frame = tk.Frame(self.preview_frame.preview_container)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            text_frame, wrap=tk.WORD, font=("Courier", 10), bg="white", state=tk.NORMAL
        )
        scrollbar = tk.Scrollbar(text_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget.insert(tk.END, initial_text)
        text_widget.config(state=tk.DISABLED)

    def select_directory(self):
        """Выбирает директорию с проектами"""
        directory = filedialog.askdirectory(title="Выберите директорию с проектами")
        if not directory:
            return

        self.msa_directory = directory
        self.status_var.set("Сканирование директории...")

        # Сканируем в отдельном потоке
        threading.Thread(target=self._scan_directory_thread, daemon=True).start()

    def _scan_directory_thread(self):
        """Фоновое сканирование директории"""
        msa, rs10 = self.extractor.scan_directory(self.msa_directory)
        self.update_queue.put(("scan_complete", (msa, rs10)))

    def on_type_change(self, *args):
        """Обработчик смены типа проектов"""
        self.update_project_display()

    def update_project_display(self):
        """Обновляет отображение проектов"""
        # Очищаем
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.project_vars = {}

        # Выбираем список в зависимости от типа
        if self.project_type_var.get() == "msa":
            projects = self.msa_projects
            self.projects_frame.config(text="Проекты MSA")
        else:
            projects = self.rs10_projects
            self.projects_frame.config(text="Проекты RS10")

        # Создаем чекбоксы
        for project in sorted(projects):
            var = tk.BooleanVar()
            self.project_vars[project] = var
            cb = ttk.Checkbutton(
                self.scrollable_frame,
                text=project,
                variable=var,
                command=self.on_selection_change,
            )
            cb.pack(anchor=tk.W, pady=2)

    def on_selection_change(self):
        """Обработчик изменения выбора проектов"""
        selected = [p for p, var in self.project_vars.items() if var.get()]

        if selected:
            self.status_var.set(
                f"Выбрано проектов: {len(selected)}. Загрузка данных..."
            )
            self.preview_frame.clear()
            threading.Thread(
                target=self._load_projects_thread, args=(selected,), daemon=True
            ).start()
        else:
            self.show_initial_preview()
            self.status_var.set("Готов к работе")

    def _load_projects_thread(self, selected_projects):
        """Фоновая загрузка данных проектов"""
        try:
            self.update_queue.put(("status", "Загрузка данных проектов..."))
            projects = []

            for proj_name in selected_projects:
                proj_path = os.path.join(self.msa_directory, proj_name)
                proj_type = self.project_type_var.get()

                # Извлекаем данные (точки загружаются без финальной типизации)
                project = self.extractor.extract_project_data(
                    proj_path, proj_name, proj_type
                )
                projects.append(project)

            self.update_queue.put(("status", "Выбор опорных и контрольных точек..."))
            result = self.extractor.finalize_point_selection(
                projects,
                self.project_type_var.get(),
                gui_callback=self._handle_incomplete_html_structure,
            )

            if result is None:
                self.update_queue.put(("status", "Обработка отменена пользователем"))
                return

            projects = result
            if not projects:
                self.update_queue.put(("status", "Нет проектов для обработки"))
                # Снимаем галочки с проектов, которые не прошли
                self.root.after(0, lambda: self._uncheck_projects(selected_projects))
                return

            # Проверяем, были ли исключены какие-то проекты
            processed_names = {p.name for p in projects}
            excluded = [n for n in selected_projects if n not in processed_names]
            if excluded:
                self.root.after(0, lambda: self._uncheck_projects(excluded))

            for i, project in enumerate(projects):
                self.update_queue.put(
                    ("status", f"Обработка проекта {i + 1}/{len(projects)}...")
                )

                # Рассчитываем статистику
                self.stat_calc.calculate(project)

                # Строим графики
                self.graph_builder.create_control_graph(project)
                self.graph_builder.create_check_graph(project)

                # Строим карту
                self.map_builder.create_map(
                    project, use_osm=self.use_osm_maps.get(), width=10, height=7
                )

            # Объединяем для мультивыбора
            self.update_queue.put(("status", "Формирование отчета..."))
            if len(projects) > 1:
                combined = self.extractor.combine_projects(projects)
                combined.statistics = self.stat_calc.calculate_combined(projects)

                # Создаем графики и карту для объединенного проекта
                self.graph_builder.create_control_graph(combined)
                self.graph_builder.create_check_graph(combined)
                self.map_builder.create_map(
                    combined, use_osm=self.use_osm_maps.get(), width=10, height=7
                )

                self.current_project = combined
            else:
                self.current_project = projects[0]

            # Генерируем отчет
            html_content = self.filler.fill_report(
                self.current_project, use_html_tables=self.use_html_tables.get()
            )

            self.update_queue.put(("report_ready", html_content))
            self.update_queue.put(("status", "Готово"))

        except Exception as e:
            self.update_queue.put(("status", f"Ошибка: {str(e)}"))
            import traceback

            traceback.print_exc()

    def select_all(self):
        """Выбирает все проекты"""
        for var in self.project_vars.values():
            var.set(True)
        self.on_selection_change()

    def deselect_all(self):
        """Снимает выбор со всех проектов"""
        for var in self.project_vars.values():
            var.set(False)
        self.on_selection_change()

    def generate_report(self):
        """Генерирует отчет (перегенерация)"""
        if not self.current_project:
            messagebox.showwarning("Предупреждение", "Сначала выберите проекты")
            return

        # Перегенерируем отчет
        html_content = self.filler.fill_report(
            self.current_project, use_html_tables=self.use_html_tables.get()
        )
        self.preview_frame.show_html(html_content)
        self.status_var.set("Отчет сгенерирован")

    def save_html_report(self):
        """Сохраняет HTML отчет в файл"""
        if not self.preview_frame.html_content:
            messagebox.showwarning("Предупреждение", "Сначала сгенерируйте отчет")
            return
        self.preview_frame.save_html()

    def regenerate_report_with_current_settings(self):
        """Перегенерирует отчет с текущими настройками, включая чекбокс OSM"""
        if not self.current_project:
            messagebox.showwarning("Предупреждение", "Сначала выберите проекты")
            return

        # Перестраиваем карту с учетом текущего состояния чекбокса OSM
        # Просто перестраиваем карту для текущего проекта, используя текущее состояние чекбокса
        self.map_builder.create_map(
            self.current_project, use_osm=self.use_osm_maps.get(), width=10, height=7
        )

        # Перегенерируем отчет
        html_content = self.filler.fill_report(
            self.current_project, use_html_tables=self.use_html_tables.get()
        )
        self.preview_frame.show_html(html_content)
        self.status_var.set("Отчет обновлен с текущими настройками")

    def export_to_pdf(self):
        """Экспортирует отчет в PDF"""
        if not self.current_project:
            messagebox.showwarning("Предупреждение", "Сначала выберите проекты")
            return

        if not self.preview_frame.html_content:
            messagebox.showwarning("Предупреждение", "Сначала сгенерируйте отчет")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Сохранить отчет в PDF",
        )

        if file_path:
            self.status_var.set("Экспорт в PDF...")

            def export_thread():
                success = self.exporter.export_to_pdf(
                    self.preview_frame.html_content, file_path
                )
                if success:
                    self.update_queue.put(
                        ("status", f"PDF сохранен: {os.path.basename(file_path)}")
                    )
                    if messagebox.askyesno("Готово", "PDF сохранен. Открыть файл?"):
                        webbrowser.open(file_path)
                else:
                    self.update_queue.put(("status", "Ошибка экспорта в PDF"))
                    messagebox.showerror(
                        "Ошибка", "Не удалось создать PDF."
                    )

            threading.Thread(target=export_thread, daemon=True).start()

    def export_to_word(self):
        """Экспортирует отчет в Word с сохранением форматирования"""
        if not self.current_project:
            messagebox.showwarning("Предупреждение", "Сначала выберите проекты")
            return

        if not self.preview_frame.html_content:
            messagebox.showwarning("Предупреждение", "Сначала сгенерируйте отчет")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[
                ("Word Document (*.docx)", "*.docx"),
                ("Word Document (*.doc)", "*.doc"),
                ("MHTML File (*.mht)", "*.mht"),
                ("HTML File (*.html)", "*.html"),
            ],
            title="Сохранить отчет в Word",
        )

        if file_path:
            self.status_var.set("Экспорт в Word...")

            def export_thread():
                # Используем улучшенный экспорт
                success = self.exporter.export_to_word_enhanced(
                    self.preview_frame.html_content, file_path
                )
                if success:
                    self.update_queue.put(
                        ("status", f"Документ сохранен: {os.path.basename(file_path)}")
                    )
                    if messagebox.askyesno(
                        "Готово", "Документ сохранен. Открыть файл?"
                    ):
                        webbrowser.open(file_path)
                else:
                    self.update_queue.put(("status", "Ошибка экспорта в Word"))
                    messagebox.showerror("Ошибка", "Не удалось сохранить документ")

            threading.Thread(target=export_thread, daemon=True).start()

    def export_to_jpeg(self):
        """Экспортирует отчет в JPEG"""
        if not self.current_project:
            messagebox.showwarning("Предупреждение", "Сначала выберите проекты")
            return

        if not self.preview_frame.html_content:
            messagebox.showwarning("Предупреждение", "Сначала сгенерируйте отчет")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[
                ("JPEG Image (*.jpg)", "*.jpg"),
                ("JPEG Image (*.jpeg)", "*.jpeg"),
            ],
            title="Сохранить страницы отчета в JPEG (будут добавлены суффиксы _001, _002...)",
        )

        if file_path:
            self.status_var.set("Экспорт в JPEG...")

            def export_thread():
                success = self.exporter.export_to_jpeg(
                    self.preview_frame.html_content, file_path
                )
                if success:
                    base, _ = os.path.splitext(file_path)
                    self.update_queue.put(
                        ("status", f"JPEG сохранен: {os.path.basename(base)}_001.jpg ...")
                    )
                    messagebox.showinfo("Готово", "Страницы отчета сохранены в JPEG")
                else:
                    self.update_queue.put(("status", "Ошибка экспорта в JPEG"))
                    messagebox.showerror("Ошибка", "Не удалось сохранить JPEG.")

            threading.Thread(target=export_thread, daemon=True).start()

    def check_update_queue(self):
        """Проверяет очередь обновлений из потоков"""
        try:
            while True:
                msg = self.update_queue.get_nowait()
                if msg[0] == "scan_complete":
                    self.msa_projects, self.rs10_projects = msg[1]
                    if not self.msa_projects and self.rs10_projects:
                        self.project_type_var.set("rs10")
                    elif not self.rs10_projects and self.msa_projects:
                        self.project_type_var.set("msa")
                    self.update_project_display()
                    msg_text = f"Найдено MSA: {len(self.msa_projects)}, RS10: {len(self.rs10_projects)}"
                    self.status_var.set(msg_text)
                    messagebox.showinfo("Результаты поиска", msg_text)
                elif msg[0] == "report_ready":
                    self.preview_frame.show_html(msg[1])
                elif msg[0] == "status":
                    self.status_var.set(msg[1])
                elif msg[0] == "html_structure_choice":
                    # Сохраняем выбор пользователя для использования в потоке
                    self.last_html_structure_choice = msg[1]
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_update_queue)

    def _handle_incomplete_html_structure(self, projects_with_issues):
        """
        Обработчик: в проектах MSA нет контрольных точек

        Returns:
            tuple: (choice, cancelled_names)
        """
        total = len(projects_with_issues)
        all_projects = any(
            getattr(p, "_all_projects_count", None) == total
            for p in projects_with_issues
        )

        if total == 1:
            preamble = f"В проекте {projects_with_issues[0].name} отсутствуют контрольные точки."
        else:
            preamble = f"Во всех {total} проектах отсутствуют контрольные точки."

        projects_text = "\n".join(
            [f"• {p.name}" for p in projects_with_issues]
        )

        if total == 1:
            message = preamble
        else:
            message = preamble + "\n\n" + projects_text

        message += "\n\nВыберите способ обработки:"

        dialog = tk.Toplevel(self.root)
        dialog.title("Отсутствуют контрольные точки")
        dialog.transient(self.root)
        dialog.grab_set()

        user_choice = tk.StringVar(value="")

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            main_frame, wrap=tk.WORD, font=("Arial", 10), height=4, width=60
        )
        text_widget.pack(fill=tk.X, pady=(0, 10))
        text_widget.insert(tk.END, message)
        text_widget.config(state=tk.DISABLED)

        choices_frame = ttk.LabelFrame(
            main_frame, text="Выберите вариант:", padding="8"
        )
        choices_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Radiobutton(
            choices_frame,
            text="Оставить как есть (все точки будут опорными)",
            variable=user_choice,
            value="keep",
        ).pack(anchor=tk.W, pady=2)

        ttk.Radiobutton(
            choices_frame,
            text="Назначить автоматически (часть точек станут контрольными)",
            variable=user_choice,
            value="algorithm",
        ).pack(anchor=tk.W, pady=2)

        ttk.Radiobutton(
            choices_frame,
            text="Отменить обработку таких отчетов",
            variable=user_choice,
            value="cancel",
        ).pack(anchor=tk.W, pady=2)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        result = {"choice": None}

        def on_ok():
            c = user_choice.get()
            if c:
                result["choice"] = c
                dialog.destroy()

        def on_cancel():
            result["choice"] = None
            dialog.destroy()

        ok_button = ttk.Button(
            buttons_frame, text="OK", command=on_ok, state=tk.DISABLED
        )
        ok_button.pack(side=tk.RIGHT, padx=5)

        ttk.Button(buttons_frame, text="Отмена", command=on_cancel).pack(
            side=tk.RIGHT, padx=5
        )

        def check_choice(*args):
            ok_button.config(state=tk.NORMAL if user_choice.get() else tk.DISABLED)

        user_choice.trace("w", check_choice)

        dialog.update_idletasks()
        # Фиксированный размер: ширина 500, высота по содержимому
        dialog.geometry("500x{0}".format(dialog.winfo_reqheight() + 40))
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        )
        dialog.geometry(f"+{x}+{y}")
        dialog.resizable(False, False)

        self.root.wait_window(dialog)

        choice = result["choice"] if result["choice"] else "cancel"

        if choice == "cancel":
            cancelled_names = [p.name for p in projects_with_issues]
        else:
            cancelled_names = []

        return choice, cancelled_names

    def _uncheck_projects(self, names):
        """Снимает галочки с проектов"""
        for name in names:
            if name in self.project_vars:
                self.project_vars[name].set(False)

    def on_closing(self):
        """Обработчик закрытия окна"""
        try:
            # Очищаем временные файлы
            if hasattr(self, "filler"):
                self.filler.cleanup_temp_files()

            # Закрываем окно (только если оно еще существует)
            if self.root and self.root.winfo_exists():
                self.root.quit()
        except (tk.TclError, RuntimeError, AttributeError):
            # Игнорируем ошибки при закрытии
            pass
