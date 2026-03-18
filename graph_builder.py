"""
Модуль для построения графиков отклонений (шаг 6).
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import tempfile
import os
from typing import Optional

from data_models import ProjectData, ControlPoint
from constants import GRAPH_SETTINGS, TOLERANCES


class GraphBuilder:
    """Строит графики отклонений"""
    
    def create_control_graph(self, project: ProjectData) -> Optional[str]:
        """Создает график для опорных точек (4.4.1)"""
        gcps = project.get_gcps()
        if not gcps or not any(p.dx is not None for p in gcps):
            return None
        
        return self._create_hv_plot(gcps, is_control=True, project=project)
    
    def create_check_graph(self, project: ProjectData) -> Optional[str]:
        """Создает график для контрольных точек (4.4.2)"""
        checkpoints = project.get_checkpoints()
        if not checkpoints or not any(p.dx is not None for p in checkpoints):
            return None
        
        return self._create_hv_plot(checkpoints, is_control=False, project=project)
    
    def _create_hv_plot(self, points: list, is_control: bool,
                        project: ProjectData) -> str:
        """
        Создает график отклонений в плане и по высоте
        """
        # Собираем данные
        ds_vals = []  # Для графика в плане (2D расстояние)
        dz_vals = []  # Для графика по высоте
        
        for p in points:
            if p.dist_2d is not None:
                ds_vals.append(p.dist_2d)
            if p.dz is not None:
                dz_vals.append(abs(p.dz))
        
        if not ds_vals and not dz_vals:
            return None
        
        # Получаем значения СКП из статистики проекта
        stats = project.statistics
        if is_control:
            std_plan = stats.control_std_2d
            std_height = stats.control_std_dz
        else:
            std_plan = stats.check_std_2d
            std_height = stats.check_std_dz
        
        # Создаем график
        fig, ax = plt.subplots(figsize=GRAPH_SETTINGS['figure_size'])
        
        x_positions = np.arange(len(points))
        
        # Рисуем отклонения в плане
        if ds_vals:
            ax.plot(x_positions[:len(ds_vals)], ds_vals,
                   marker='o', linestyle='-', linewidth=GRAPH_SETTINGS['line_width'],
                   markersize=GRAPH_SETTINGS['marker_size'], color='blue',
                   label='Отклонения в плане')
            
            # СКП в плане (используем значение из статистики - RMSE)
            ax.axhline(y=std_plan, color='blue', linestyle='-.',
                      linewidth=2, alpha=0.7,
                      label=f'СКП в плане = {std_plan:.3f} м')
        
        # Рисуем отклонения по высоте
        if dz_vals:
            ax.plot(x_positions[:len(dz_vals)], dz_vals,
                   marker='o', linestyle='-', linewidth=GRAPH_SETTINGS['line_width'],
                   markersize=GRAPH_SETTINGS['marker_size'], color='green',
                   label='Отклонения по высоте')
            
            # СКП по высоте (используем значение из статистики - стандартное отклонение)
            ax.axhline(y=std_height, color='green', linestyle='-.',
                      linewidth=2, alpha=0.7,
                      label=f'СКП по высоте = {std_height:.3f} м')
        
        ax.set_xlabel('Номер точки', fontsize=12)
        ax.set_ylabel('Отклонения (м)', fontsize=12)
        ax.set_ylim(bottom=0)
        
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.3)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        ax.legend(loc='upper right', fontsize=10)
        
        ax.set_xticks(x_positions)
        ax.set_xticklabels([str(i+1) for i in x_positions])
        
        plt.tight_layout()
        
        # Сохраняем
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        output_path = temp_file.name
        temp_file.close()
        
        plt.savefig(output_path, dpi=GRAPH_SETTINGS['dpi'], bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        
        if is_control:
            project.control_graph_path = output_path
        else:
            project.check_graph_path = output_path
        
        return output_path
    
    def create_combined_graphs(self, projects: list) -> dict:
        """Создает объединенные графики для нескольких проектов"""
        result = {
            'control': None,
            'check': None
        }
        
        # Собираем все опорные точки
        all_gcps = []
        for p in projects:
            all_gcps.extend(p.gcps)
        
        if all_gcps and any(p.dx is not None for p in all_gcps):
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            result['control'] = self._create_hv_plot(
                all_gcps, is_control=True, 
                project=projects[0]  # просто для сохранения пути
            )
        
        # Собираем все контрольные точки
        all_checks = []
        for p in projects:
            all_checks.extend(p.checkpoints)
        
        if all_checks and any(p.dx is not None for p in all_checks):
            result['check'] = self._create_hv_plot(
                all_checks, is_control=False,
                project=projects[0]
            )
        
        return result