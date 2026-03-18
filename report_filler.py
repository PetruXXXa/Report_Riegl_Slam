"""
Модуль для заполнения макета отчета данными (шаг 8).
"""

import base64
import os
import datetime
import tempfile
import tkinter as tk
from tkinter import ttk, scrolledtext
import webbrowser
import pandas as pd
from typing import Dict, Any, Optional

from data_models import ProjectData, ControlPoint
from utils import FormattingUtils
from report_template import ReportTemplate


class ReportFiller:
    """Заполняет HTML шаблон данными"""
    
    def __init__(self):
        self.formatter = FormattingUtils()
        self.temp_files = []  # Для отслеживания временных файлов
    
    def fill_report(self, project: ProjectData, map_image_path: str = None,
                   use_html_tables: bool = True) -> str:
        """
        Заполняет отчет данными проекта
        """
        template = ReportTemplate.get_template()
        
        # Формируем общую статистику
        total_stats = self._format_total_stats(project)
        
        # Формируем карту
        map_html = self._format_map_image(map_image_path or project.map_image_path, project)
        
        # Формируем таблицы точек
        points_tables = self._format_points_tables(project, use_html_tables)
        
        # Формируем таблицы отклонений
        control_deviations = self._format_deviations_table(project.get_gcps(), "Опорные точки")
        check_deviations = self._format_deviations_table(project.get_checkpoints(), "Контрольные точки")
        
        # Формируем таблицы статистики
        control_stats = self._format_stats_table(project.statistics.to_dataframe_control(), "Опорные точки")
        check_stats = self._format_stats_table(project.statistics.to_dataframe_check(), "Контрольные точки")
        
        # Формируем графики
        control_graph = self._format_graph_image(project.control_graph_path)
        check_graph = self._format_graph_image(project.check_graph_path)
        
        # Заполняем шаблон
        filled = template.format(
            generation_date=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
            total_stats=total_stats,
            map_image=map_html,
            points_tables=points_tables,
            control_deviations_table=control_deviations,
            control_stats_table=control_stats,
            control_graph=control_graph,
            check_deviations_table=check_deviations,
            check_stats_table=check_stats,
            check_graph=check_graph
        )
        
        return filled
    
    def save_html_to_temp(self, html_content: str) -> str:
        """Сохраняет HTML во временный файл и возвращает путь"""
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.html', 
            delete=False, 
            mode='w', 
            encoding='utf-8'
        )
        temp_path = temp_file.name
        temp_file.write(html_content)
        temp_file.close()
        
        self.temp_files.append(temp_path)
        return temp_path
    
    def cleanup_temp_files(self):
        """Очищает временные файлы"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass
        self.temp_files = []
    
    def create_preview_widget(self, parent, html_content):
        """
        Создает виджет для полного HTML предпросмотра (только содержимое без тулбара)
        """
        try:
            import tkinterweb
            has_tkinterweb = True
        except ImportError:
            has_tkinterweb = False
        
        if has_tkinterweb:
            return self._create_html_preview_content(parent, html_content)
        else:
            return self._create_fallback_preview_content(parent, html_content)
    
    def _create_html_preview(self, parent, html_content):
        """Создает полноценный HTML предпросмотр с tkinterweb"""
        # Создаем фрейм с тулбаром
        preview_frame = tk.Frame(parent)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Тулбар
        toolbar = tk.Frame(preview_frame, bg='#f0f0f0', height=30)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        
        # Сохраняем HTML во временный файл
        temp_path = self.save_html_to_temp(html_content)
        
        # Создаем общие кнопки
        open_btn, save_btn = self._create_toolbar_buttons(toolbar, html_content, temp_path)
        
        # Кнопка обновить для HTML предпросмотра
        refresh_btn = tk.Button(toolbar, text="Обновить",
                               command=lambda: html_frame.load_html(html_content))
        refresh_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        # HTML фрейм
        import tkinterweb
        html_frame = tkinterweb.HtmlFrame(preview_frame, messages_enabled=False)
        html_frame.pack(fill=tk.BOTH, expand=True)
        html_frame.load_html(html_content)
        
        return preview_frame, temp_path
    
    def _create_fallback_preview(self, parent, html_content):
        """Создает упрощенный предпросмотр (если нет tkinterweb)"""
        preview_frame = tk.Frame(parent)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Тулбар
        toolbar = tk.Frame(preview_frame, bg='#f0f0f0', height=30)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        
        # Сохраняем во временный файл
        temp_path = self.save_html_to_temp(html_content)
        
        # Создаем общие кнопки
        open_btn, save_btn = self._create_toolbar_buttons(toolbar, html_content, temp_path)
        
        # Текстовый виджет для упрощенного просмотра
        text_frame = tk.Frame(preview_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='white'
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Вставляем упрощенный предросмотр
        preview_text = self._create_preview_text(html_content)
        text_widget.insert(tk.END, preview_text)
        text_widget.config(state=tk.DISABLED)
        
        return preview_frame, temp_path
    
    def _create_html_preview_content(self, parent, html_content):
        """Создает только содержимое HTML предпросмотра без тулбара"""
        # Создаем фрейм для содержимого
        content_frame = tk.Frame(parent)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Сохраняем HTML во временный файл
        temp_path = self.save_html_to_temp(html_content)
        
        # HTML фрейм
        import tkinterweb
        html_frame = tkinterweb.HtmlFrame(content_frame, messages_enabled=False)
        html_frame.pack(fill=tk.BOTH, expand=True)
        html_frame.load_html(html_content)
        
        return content_frame, temp_path
    
    def _create_fallback_preview_content(self, parent, html_content):
        """Создает только содержимое упрощенного предпросмотра без тулбара"""
        content_frame = tk.Frame(parent)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Текстовый виджет для упрощенного просмотра
        text_widget = scrolledtext.ScrolledText(
            content_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='white'
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Вставляем упрощенный предпросмотр
        preview_text = self._create_preview_text(html_content)
        text_widget.insert(tk.END, preview_text)
        text_widget.config(state=tk.DISABLED)
        
        return content_frame, None
    
    def _create_toolbar_buttons(self, parent, html_content, temp_path):
        """Создает общие кнопки тулбара для предпросмотра"""
        open_btn = tk.Button(parent, text="Открыть в браузере",
                            command=lambda: webbrowser.open('file://' + temp_path))
        open_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        save_btn = tk.Button(parent, text="Сохранить HTML",
                            command=lambda: self._save_html_dialog(html_content))
        save_btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        return open_btn, save_btn
    
    def _save_html_dialog(self, html_content):
        """Диалог сохранения HTML"""
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            title="Сохранить HTML отчет"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                return file_path
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")
        return None
    
    def _create_preview_text(self, html_content: str) -> str:
        """Создает упрощенный текстовый предпросмотр"""
        preview = "=" * 60 + "\n"
        preview += "           ПРЕДПРОСМОТР HTML ОТЧЕТА\n"
        preview += "=" * 60 + "\n\n"
        preview += "Для полного просмотра с изображениями:\n"
        preview += "1. Установите библиотеку tkinterweb (pip install tkinterweb)\n"
        preview += "2. Или нажмите кнопку 'Открыть в браузере'\n\n"
        preview += "=" * 60 + "\n\n"
        
        import re
        
        # Извлекаем общую статистику
        stats_match = re.findall(r'<span class="text-stat-label">(.*?)</span>\s*<span class="text-stat-value">(.*?)</span>', html_content)
        if stats_match:
            preview += "📊 ОБЩАЯ СТАТИСТИКА:\n"
            preview += "-" * 40 + "\n"
            for label, value in stats_match:
                preview += f"{label:30} {value}\n"
            preview += "\n"
        
        # Таблицы
        tables = re.findall(r'<h4>(.*?)</h4>', html_content)
        if tables:
            preview += "📋 ТАБЛИЦЫ:\n"
            preview += "-" * 40 + "\n"
            for title in tables[:5]:
                preview += f"• {title}\n"
            if len(tables) > 5:
                preview += f"  и еще {len(tables) - 5} таблиц...\n"
            preview += "\n"
        
        return preview
    
    def _format_total_stats(self, project: ProjectData) -> str:
        """Форматирует блок общей статистики"""
        html = ""
        
        if project.project_type == "rs10":
            html += f"""
                <div class="text-stat-item">
                    <span class="text-stat-label">Общая длина траектории:</span>
                    <span class="text-stat-value">{int(project.total_trajectory_length)} м</span>
                </div>
            """
        else:
            html += f"""
                <div class="text-stat-item">
                    <span class="text-stat-label">Всего станций сканирования:</span>
                    <span class="text-stat-value">{project.total_stations}</span>
                </div>
            """
        
        html += f"""
            <div class="text-stat-item">
                <span class="text-stat-label">Опорных точек:</span>
                <span class="text-stat-value">{project.gcp_count}</span>
            </div>
            <div class="text-stat-item">
                <span class="text-stat-label">Контрольных точек:</span>
                <span class="text-stat-value">{project.checkpoint_count}</span>
            </div>
        """
        
        return html
    
    def _format_map_image(self, image_path: str, project=None) -> str:
        """Форматирует изображение карты"""
        if not image_path or not os.path.exists(image_path):
            return '<p>Карта не доступна</p>'
        
        try:
            with open(image_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            
            img_tag = f'<img src="data:image/png;base64,{img_data}" alt="Схема расположения точек" style="width:100%; height:auto;">'
            
            # Добавляем подпись только если использовалась OSM подложка
            caption = ''
            if project and hasattr(project, 'used_osm_map') and project.used_osm_map:
                caption = '<div class="map-caption">Данные карты © OpenStreetMap contributors</div>'
            
            return f'<div class="map-container">{img_tag}{caption}</div>'
        except:
            return '<p>Ошибка загрузки карты</p>'
    
    def _format_graph_image(self, image_path: str) -> str:
        """Форматирует изображение графика"""
        if not image_path or not os.path.exists(image_path):
            return '<p>График не доступен</p>'
        
        try:
            with open(image_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            
            return f'<img src="data:image/png;base64,{img_data}" alt="График отклонений" style="width:100%; height:auto;">'
        except:
            return '<p>Ошибка загрузки графика</p>'
    
    def _format_points_tables(self, project: ProjectData, use_html: bool) -> str:
        """Форматирует таблицы опорных и контрольных точек"""
        html = ""
        
        # Таблица опорных точек
        if project.get_gcps():
            df = self._create_points_dataframe(project.get_gcps(), is_control=True)
            html += self._df_to_html_table(df, "Опорные точки")
        
        # Таблица контрольных точек
        if project.get_checkpoints():
            df = self._create_points_dataframe(project.get_checkpoints(), is_control=False)
            html += self._df_to_html_table(df, "Контрольные точки")
        
        if not html:
            html = '<p>Таблицы не найдены</p>'
        
        return html
    
    def _create_points_dataframe(self, points: list, is_control: bool) -> pd.DataFrame:
        """Создает DataFrame с координатами точек"""
        data = []
        for p in points:
            data.append({
                'Имя': p.name,
                'X (м)': self.formatter.format_number(p.x_table, 3),
                'Y (м)': self.formatter.format_number(p.y_table, 3),
                'Z (м)': self.formatter.format_number(p.z_table, 3)
            })
        return pd.DataFrame(data)
    
    def _format_deviations_table(self, points: list, title: str) -> str:
        """Форматирует таблицу отклонений"""
        if not points:
            return f'<p>Данные отклонений для {title} не найдены</p>'
        
        # Фильтруем только точки с отклонениями
        points_with_deviations = [p for p in points if p.dx is not None]
        
        if not points_with_deviations:
            return f'<p>Нет данных отклонений для {title}</p>'
        
        data = []
        for i, p in enumerate(points_with_deviations, 1):
            data.append({
                '№': i,
                'Имя': p.name,
                'dX (м)': self.formatter.format_number(p.dx, 3),
                'dY (м)': self.formatter.format_number(p.dy, 3),
                'dZ (м)': self.formatter.format_number(p.dz, 3),
                '2D_dist (м)': self.formatter.format_number(p.dist_2d, 3),
                '3D_dist (м)': self.formatter.format_number(p.dist_3d, 3)
            })
        
        df = pd.DataFrame(data)
        return self._df_to_html_table(df, f"Отклонения {title}")
    
    def _format_stats_table(self, df: pd.DataFrame, title: str) -> str:
        """Форматирует таблицу статистики"""
        if df.empty:
            return f'<p>Статистика для {title} не найдена</p>'
        
        # Удаляем пятую строку (MAD) из таблицы
        df_filtered = df[df['Метрика'] != 'MAD'].copy()

        # Преобразуем названия метрик
        metric_map = {
            'Min': 'Минимальное отклонение',
            'Max': 'Максимальное отклонение',
            'Mean': 'Среднее отклонение',
            'Std Dev': 'Средняя квадратическая погрешность (СКП)'
        }

        df_display = df_filtered.copy()
        df_display['Метрика'] = df_display['Метрика'].map(metric_map).fillna(df_display['Метрика'])
        
        # Форматируем числа
        for col in ['dX', 'dY', 'dZ', '2D_dist', '3D_dist']:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(
                    lambda x: self.formatter.format_number(x, 3) if pd.notna(x) else '---'
                )
        
        return self._df_to_html_table(df_display, f"Статистика {title}")
    
    def _df_to_html_table(self, df: pd.DataFrame, title: str) -> str:
        """Конвертирует DataFrame в HTML таблицу"""
        html = f'<h4>{title}</h4>\n'
        html += '<div class="table-container">\n'
        html += '<table class="accuracy-table">\n'
        
        # Заголовки
        html += '<thead>\n<tr>\n'
        for col in df.columns:
            html += f'<th>{col}</th>\n'
        html += '</tr>\n</thead>\n'
        
        # Данные
        html += '<tbody>\n'
        for _, row in df.iterrows():
            html += '<tr>\n'
            for val in row:
                html += f'<td>{val}</td>\n'
            html += '</tr>\n'
        html += '</tbody>\n</table>\n'
        html += '</div>\n'
        
        return html