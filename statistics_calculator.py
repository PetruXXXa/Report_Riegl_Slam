"""
Модуль для расчета статистических показателей (шаг 5).
"""

import numpy as np
from scipy.stats import median_abs_deviation
from typing import List
from data_models import ProjectData, ControlPoint, StatisticsData


class StatisticsCalculator:
    """Вычисляет статистику по отклонениям точек"""
    
    @staticmethod
    def calculate(project: ProjectData) -> StatisticsData:
        """Вычисляет статистику для проекта"""
        stats = StatisticsData()
        
        # Получаем все точки с отклонениями
        all_points_with_deviations = [p for p in project.control_points if p.dx is not None]
        print(f"Всего точек с отклонениями: {len(all_points_with_deviations)}")
        
        # Опорные точки (согласно алгоритму выбора)
        gcps = [p for p in all_points_with_deviations if p.is_gcp]
        if gcps:
            print(f"Опорных точек с отклонениями: {len(gcps)}")
            stats = StatisticsCalculator._calculate_for_points(gcps, is_control=True)
        
        # Контрольные точки (согласно алгоритму выбора)
        checkpoints = [p for p in all_points_with_deviations if not p.is_gcp]
        if checkpoints:
            print(f"Контрольных точек с отклонениями: {len(checkpoints)}")
            check_stats = StatisticsCalculator._calculate_for_points(checkpoints, is_control=False)
            
            # Объединяем статистики
            for attr in dir(check_stats):
                if not attr.startswith('_') and 'check_' in attr:
                    setattr(stats, attr, getattr(check_stats, attr))
        
        project.statistics = stats
        return stats
    
    @staticmethod
    def _calculate_for_points(points: List[ControlPoint], is_control: bool) -> StatisticsData:
        """Вычисляет статистику для списка точек"""
        stats = StatisticsData()
        
        # Собираем значения
        dx_vals = [p.dx for p in points if p.dx is not None]
        dy_vals = [p.dy for p in points if p.dy is not None]
        dz_vals = [p.dz for p in points if p.dz is not None]
        dist_2d_vals = [p.dist_2d for p in points if p.dist_2d is not None]
        dist_3d_vals = [p.dist_3d for p in points if p.dist_3d is not None]
        
        prefix = 'control' if is_control else 'check'
        
        # Min
        if dx_vals:
            setattr(stats, f'{prefix}_min_dx', np.min(dx_vals))
            setattr(stats, f'{prefix}_min_dy', np.min(dy_vals))
            setattr(stats, f'{prefix}_min_dz', np.min(dz_vals))
            setattr(stats, f'{prefix}_min_2d', np.min(dist_2d_vals) if dist_2d_vals else 0)
            setattr(stats, f'{prefix}_min_3d', np.min(dist_3d_vals) if dist_3d_vals else 0)
        
        # Max
        if dx_vals:
            setattr(stats, f'{prefix}_max_dx', np.max(dx_vals))
            setattr(stats, f'{prefix}_max_dy', np.max(dy_vals))
            setattr(stats, f'{prefix}_max_dz', np.max(dz_vals))
            setattr(stats, f'{prefix}_max_2d', np.max(dist_2d_vals) if dist_2d_vals else 0)
            setattr(stats, f'{prefix}_max_3d', np.max(dist_3d_vals) if dist_3d_vals else 0)
        
        # Mean
        if dx_vals:
            setattr(stats, f'{prefix}_mean_dx', np.mean(dx_vals))
            setattr(stats, f'{prefix}_mean_dy', np.mean(dy_vals))
            setattr(stats, f'{prefix}_mean_dz', np.mean(dz_vals))
            setattr(stats, f'{prefix}_mean_2d', np.mean(dist_2d_vals) if dist_2d_vals else 0)
            setattr(stats, f'{prefix}_mean_3d', np.mean(dist_3d_vals) if dist_3d_vals else 0)
        
        # Std Dev (для осей) и RMSE (для 2D и 3D)
        if dx_vals:
            setattr(stats, f'{prefix}_std_dx', np.std(dx_vals, ddof=0))
            setattr(stats, f'{prefix}_std_dy', np.std(dy_vals, ddof=0))
            setattr(stats, f'{prefix}_std_dz', np.std(dz_vals, ddof=0))
            
            # Вычисляем RMSE для 2D: √(Σ(dx² + dy²)/n)
            if dx_vals and dy_vals:
                rmse_2d = np.sqrt(np.mean(np.array(dx_vals)**2 + np.array(dy_vals)**2))
                setattr(stats, f'{prefix}_std_2d', rmse_2d)
            elif dist_2d_vals:
                # Альтернативно вычисляем RMSE из dist_2d_vals: √(Σ(dist_2d²)/n)
                rmse_2d = np.sqrt(np.mean(np.array(dist_2d_vals)**2))
                setattr(stats, f'{prefix}_std_2d', rmse_2d)
            else:
                setattr(stats, f'{prefix}_std_2d', 0.0)
                
            # Вычисляем RMSE для 3D: √(Σ(dx² + dy² + dz²)/n)
            if dx_vals and dy_vals and dz_vals:
                rmse_3d = np.sqrt(np.mean(np.array(dx_vals)**2 + np.array(dy_vals)**2 + np.array(dz_vals)**2))
                setattr(stats, f'{prefix}_std_3d', rmse_3d)
            elif dist_3d_vals:
                rmse_3d = np.sqrt(np.mean(np.array(dist_3d_vals)**2))
                setattr(stats, f'{prefix}_std_3d', rmse_3d)
            else:
                setattr(stats, f'{prefix}_std_3d', 0.0)
        
        # MAD
        if dx_vals:
            setattr(stats, f'{prefix}_mad_dx', median_abs_deviation(dx_vals, scale='normal'))
            setattr(stats, f'{prefix}_mad_dy', median_abs_deviation(dy_vals, scale='normal'))
            setattr(stats, f'{prefix}_mad_dz', median_abs_deviation(dz_vals, scale='normal'))
            
            if dist_2d_vals:
                setattr(stats, f'{prefix}_mad_2d', median_abs_deviation(dist_2d_vals, scale='normal'))
            
            if dist_3d_vals:
                setattr(stats, f'{prefix}_mad_3d', median_abs_deviation(dist_3d_vals, scale='normal'))
        
        return stats
    
    @staticmethod
    def calculate_combined(projects: List[ProjectData]) -> StatisticsData:
        """Вычисляет объединенную статистику для нескольких проектов"""
        if not projects:
            return StatisticsData()
        
        # Собираем все точки
        all_gcps = []
        all_checkpoints = []
        
        for p in projects:
            all_gcps.extend(p.get_gcps())
            all_checkpoints.extend(p.get_checkpoints())
        
        stats = StatisticsData()
        
        # Статистика по опорным точкам
        if all_gcps:
            control_stats = StatisticsCalculator._calculate_for_points(all_gcps, is_control=True)
            for attr in dir(control_stats):
                if attr.startswith('control_'):
                    setattr(stats, attr, getattr(control_stats, attr))
        
        # Статистика по контрольным точкам
        if all_checkpoints:
            check_stats = StatisticsCalculator._calculate_for_points(all_checkpoints, is_control=False)
            for attr in dir(check_stats):
                if attr.startswith('check_'):
                    setattr(stats, attr, getattr(check_stats, attr))
        
        return stats