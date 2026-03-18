"""
Вспомогательные утилиты для работы с координатами и форматами.
"""

import numpy as np
import math
from typing import Tuple, Optional
import pandas as pd


class CoordinateConverter:
    """Конвертер координат ECEF <-> WGS84"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CoordinateConverter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            # WGS84 эллипсоид
            self.a = 6378137.0
            self.f = 1 / 298.257223563
            self.b = self.a * (1 - self.f)
            self.e_sq = self.f * (2 - self.f)
            self._initialized = True
    
    def ecef_to_wgs84(self, x, y, z) -> Tuple[float, float, float]:
        """Конвертирует ECEF в WGS84 (широта, долгота, высота)"""
        x = np.asarray(x)
        y = np.asarray(y)
        z = np.asarray(z)
        
        lon = np.arctan2(y, x)
        p = np.sqrt(x**2 + y**2)
        
        lat = np.arctan2(z, p * (1 - self.e_sq))
        
        # Итеративное уточнение
        for _ in range(10):
            sin_lat = np.sin(lat)
            N = self.a / np.sqrt(1 - self.e_sq * sin_lat**2)
            h = p / np.cos(lat) - N
            lat_new = np.arctan2(z, p * (1 - self.e_sq * N / (N + h)))
            
            if np.abs(lat_new - lat) < 1e-12:
                lat = lat_new
                break
            lat = lat_new
        
        lat_deg = float(np.degrees(lat))
        lon_deg = float(np.degrees(lon))
        h = float(h if 'h' in locals() else p / np.cos(lat) - N)
        
        return lat_deg, lon_deg, h
    
    def apply_transform(self, coords: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Применяет матрицу трансформации к координатам"""
        if coords.ndim == 1:
            coords = coords.reshape(1, -1)
        
        homo_coords = np.hstack([coords, np.ones((coords.shape[0], 1))])
        transformed = homo_coords @ matrix.T
        return transformed[:, :3]


class PointSelector:
    """Алгоритм выбора опорных и контрольных точек"""
    
    @staticmethod
    def select_gcps(points: list, target_ratio: float = 0.5, min_gcp: int = 3) -> Tuple[list, list]:
        """
        Разделяет точки на опорные (GCP) и контрольные (checkpoints)
        Использует алгоритм farthest point sampling
        """
        n = len(points)
        if n == 0:
            return [], []
        
        # Создаем координаты для расчета расстояний
        coords = np.array([[i, 0] for i in range(n)])  # Используем индексы
        
        # Условие 1-2: начало и конец всегда опорные
        gcp_indices = {0, n-1}
        
        # Условие 3: если <= 3 точек, все опорные
        if n <= 3:
            return points, []
        
        # Условие 4: если 4 точки, то 3 опорные
        if n == 4:
            mid_candidates = [1, 2]
            gcp_indices.add(mid_candidates[0])  # Добавляем первую среднюю
            gcp_points = [points[i] for i in sorted(gcp_indices)]
            check_points = [points[i] for i in range(n) if i not in gcp_indices]
            return gcp_points, check_points
        
        # Условие 5: n >= 5
        try:
            from scipy.spatial.distance import cdist
        except ImportError:
            # Если scipy недоступен, используем простой алгоритм
            target_gcp = max(min_gcp, int(round(target_ratio * n)))
            gcp_indices.update(range(min(target_gcp-2, n-2)))  # Добавляем первые точки
            return ([points[i] for i in sorted(gcp_indices)], 
                    [points[i] for i in range(n) if i not in gcp_indices])
        
        target_gcp = max(min_gcp, int(round(target_ratio * n)))
        
        while len(gcp_indices) < target_gcp:
            remaining = [i for i in range(n) if i not in gcp_indices]
            if not remaining:
                break
            
            min_dists = []
            for i in remaining:
                dists = cdist([coords[i]], coords[list(gcp_indices)]).flatten()
                min_dists.append(np.min(dists))
            
            best_idx = remaining[np.argmax(min_dists)]
            gcp_indices.add(best_idx)
        
        gcp_points = [points[i] for i in sorted(gcp_indices)]
        check_points = [points[i] for i in range(n) if i not in gcp_indices]
        return gcp_points, check_points


class FormattingUtils:
    """Утилиты форматирования чисел"""
    
    @staticmethod
    def format_number(value, decimals: int = 4) -> str:
        """Форматирует число с заданным количеством знаков"""
        try:
            if pd.isna(value) or value is None:
                return '---'
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return str(value)