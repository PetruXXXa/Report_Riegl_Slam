"""
Модуль для поиска и извлечения данных из проектов MSA и RS10.
Реализует шаги 1-4 из описания архитектуры с улучшенным алгоритмом разделения точек.
"""

import os
import pandas as pd
import numpy as np
import re
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from io import StringIO
from scipy.spatial.distance import cdist

from data_models import ProjectData, TrajectoryData, ControlPoint
from utils import CoordinateConverter
from constants import MGGT_TO_WGS84_MATRIX, PROJECT_CLUSTER_DISTANCE


class PointSelector:
    """
    Алгоритм выбора опорных и контрольных точек с учетом:
    - Типа проекта (MSA/RS10)
    - Количества проектов (один/несколько)
    - Близости проектов (для MSA)
    """
    
    # Константы алгоритма
    TARGET_GCP_RATIO = 0.6  # Целевое соотношение опорных точек (60%)
    MIN_GCP = 3  # Минимальное количество опорных точек
    CLUSTER_DISTANCE = 20.0  # Расстояние для связывания проектов (метры)
    
    def __init__(self):
        self.converter = CoordinateConverter()
    
    def select_points(self, projects: List[ProjectData], 
                     project_type: str) -> List[ControlPoint]:
        """
        Главный метод выбора опорных и контрольных точек
        
        Args:
            projects: Список проектов
            project_type: 'msa' или 'rs10'
            
        Returns:
            Список всех точек с установленными флагами is_gcp
        """
        if project_type == "rs10":
            return self._select_rs10_points(projects)
        else:
            return self._select_msa_points(projects)
    
    def _select_rs10_points(self, projects: List[ProjectData]) -> List[ControlPoint]:
        """
        Выбор точек для RS10 проектов
        Для каждого проекта отдельно: первая и последняя точки всегда опорные
        """
        all_points = []
        
        for project in projects:
            # Получаем все точки проекта (уже извлеченные из SLAM_Refine_Report.csv)
            points = project.control_points
            if not points:
                continue
            
            n = len(points)
            
            # Правило 1: первая и последняя точки всегда опорные
            points[0].is_gcp = True
            points[-1].is_gcp = True
            
            # Если точек <= 3, все опорные
            if n <= 3:
                for i in range(n):
                    points[i].is_gcp = True
            else:
                # Целевое количество опорных
                target_gcp = max(self.MIN_GCP, int(round(self.TARGET_GCP_RATIO * n)))
                
                # Уже выбраны первая и последняя
                gcp_indices = {0, n-1}
                
                # Применяем FPS для выбора остальных
                self._farthest_point_sampling(points, gcp_indices, target_gcp)
                
                # Устанавливаем флаги
                for i, point in enumerate(points):
                    point.is_gcp = i in gcp_indices
            
            all_points.extend(points)
        
        return all_points
    
    def _select_msa_points(self, projects: List[ProjectData]) -> List[ControlPoint]:
        """
        Выбор точек для MSA проектов с учетом связности
        """
        if len(projects) == 1:
            # Одиночный проект - обрабатываем как RS10
            return self._select_rs10_points(projects)
        
        # Несколько проектов - анализируем связность
        return self._select_multiple_msa_points(projects)
    
    def _select_multiple_msa_points(self, projects: List[ProjectData]) -> List[ControlPoint]:
        """
        Выбор точек для нескольких MSA проектов с кластеризацией
        """
        # Шаг 1: Собираем все точки с информацией о проекте
        all_points_with_proj = []
        for proj_idx, project in enumerate(projects):
            points = project.control_points
            for point in points:
                all_points_with_proj.append({
                    'point': point,
                    'project_idx': proj_idx,
                    'point_idx': len([p for p in all_points_with_proj if p['project_idx'] == proj_idx])
                })
        
        if not all_points_with_proj:
            return []
        
        # Шаг 2: Формируем кластеры на основе расстояний между проектами
        clusters = self._form_clusters(projects, all_points_with_proj)
        
        # Шаг 3: Обрабатываем каждый кластер
        result_points = []
        for cluster in clusters:
            cluster_points = self._process_cluster(cluster)
            result_points.extend(cluster_points)
        
        return result_points
    
    def _form_clusters(self, projects: List[ProjectData], 
                      all_points: List[Dict]) -> List[List[Dict]]:
        """
        Формирует кластеры связанных проектов
        """
        n_projects = len(projects)
        if n_projects == 0:
            return []
        
        # Создаем граф связности
        adjacency = np.zeros((n_projects, n_projects), dtype=bool)
        
        for i in range(n_projects - 1):
            for j in range(i + 1, n_projects):
                # Проверяем расстояние между проектами
                if self._are_projects_connected(projects[i], projects[j]):
                    adjacency[i, j] = adjacency[j, i] = True
        
        # Находим связные компоненты (кластеры)
        visited = [False] * n_projects
        clusters = []
        
        for i in range(n_projects):
            if not visited[i]:
                cluster = []
                stack = [i]
                visited[i] = True
                
                while stack:
                    current = stack.pop()
                    cluster.append(current)
                    
                    for j in range(n_projects):
                        if adjacency[current, j] and not visited[j]:
                            stack.append(j)
                            visited[j] = True
                
                # Собираем все точки из проектов кластера
                cluster_points = []
                for proj_idx in cluster:
                    proj_points = [p for p in all_points if p['project_idx'] == proj_idx]
                    # Сортируем точки в порядке следования в проекте
                    proj_points.sort(key=lambda x: x['point_idx'])
                    cluster_points.extend(proj_points)
                
                clusters.append(cluster_points)
        
        return clusters
    
    def _are_projects_connected(self, proj1: ProjectData, proj2: ProjectData) -> bool:
        """
        Проверяет, связаны ли два проекта (расстояние между концом первого и началом второго < 20 м)
        """
        points1 = proj1.control_points
        points2 = proj2.control_points
        
        if not points1 or not points2:
            return False
        
        # Последняя точка первого проекта
        last_p1 = points1[-1]
        # Первая точка второго проекта
        first_p2 = points2[0]
        
        # Вычисляем расстояние (используем координаты для схемы, если есть, иначе исходные)
        if last_p1.x_map is not None and first_p2.x_map is not None:
            x1, y1, z1 = last_p1.x_map, last_p1.y_map, last_p1.z_map
            x2, y2, z2 = first_p2.x_map, first_p2.y_map, first_p2.z_map
        else:
            x1, y1, z1 = last_p1.x, last_p1.y, last_p1.z
            x2, y2, z2 = first_p2.x, first_p2.y, first_p2.z
        
        distance = np.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
        
        return distance < self.CLUSTER_DISTANCE
    
    def _process_cluster(self, cluster_points: List[Dict]) -> List[ControlPoint]:
        """
        Обрабатывает кластер точек, выбирая опорные и контрольные
        """
        n = len(cluster_points)
        if n == 0:
            return []
        
        # Извлекаем сами точки
        points = [item['point'] for item in cluster_points]
        
        # Правило для кластера: только первая и последняя точки кластера - опорные
        points[0].is_gcp = True
        points[-1].is_gcp = True
        
        # Если точек <= 3, все опорные
        if n <= 3:
            for i in range(n):
                points[i].is_gcp = True
            return points
        
        # Целевое количество опорных
        target_gcp = max(self.MIN_GCP, int(round(self.TARGET_GCP_RATIO * n)))
        
        # Уже выбраны первая и последняя
        gcp_indices = {0, n-1}
        
        # Применяем FPS для выбора остальных
        self._farthest_point_sampling(points, gcp_indices, target_gcp)
        
        # Устанавливаем флаги
        for i, point in enumerate(points):
            point.is_gcp = i in gcp_indices
        
        return points
    
    def _farthest_point_sampling(self, points: List[ControlPoint], 
                                 gcp_indices: set, target_gcp: int):
        """
        Алгоритм farthest point sampling для равномерного выбора опорных точек
        """
        if len(points) == 0:
            return
        
        # Подготавливаем координаты для расчета расстояний
        coords = []
        for p in points:
            # Используем координаты для схемы, если есть, иначе исходные
            if p.x_map is not None:
                coords.append([p.x_map, p.y_map, p.z_map])
            else:
                coords.append([p.x, p.y, p.z])
        
        coords = np.array(coords)
        
        # Продолжаем, пока не наберем нужное количество
        while len(gcp_indices) < target_gcp:
            remaining = [i for i in range(len(points)) if i not in gcp_indices]
            if not remaining:
                break
            
            # Для каждой оставшейся точки находим минимальное расстояние до выбранных
            min_dists = []
            for i in remaining:
                dists = cdist([coords[i]], coords[list(gcp_indices)]).flatten()
                min_dists.append(np.min(dists))
            
            # Выбираем точку с максимальным минимальным расстоянием
            best_idx = remaining[np.argmax(min_dists)]
            gcp_indices.add(best_idx)


class DataExtractor:
    """Извлекает данные из файлов проектов"""
    
    def __init__(self):
        self.converter = CoordinateConverter()
        self.selector = PointSelector()
    
    def scan_directory(self, directory: str) -> Tuple[List[str], List[str]]:
        """
        Сканирует директорию и возвращает списки проектов MSA и RS10
        """
        msa_projects = []
        rs10_projects = []
        
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if not os.path.isdir(item_path):
                continue
            
            # MSA проект
            if item.startswith("MSA2-") and item.endswith("-log"):
                msa_projects.append(item)
            
            # RS10 проект (содержит папку AUTOSOLVE)
            elif os.path.exists(os.path.join(item_path, "AUTOSOLVE")):
                rs10_projects.append(item)
        
        return msa_projects, rs10_projects
    
    def extract_project_data(self, project_path: str, project_name: str, 
                            project_type: str) -> ProjectData:
        """
        Извлекает все данные из проекта (шаги 1-4)
        """
        project = ProjectData(
            name=project_name,
            path=project_path,
            project_type=project_type
        )
        
        # Шаг 1: Извлекаем траекторию
        self._extract_trajectory(project)
        
        # Шаг 2: Извлекаем опорные и контрольные точки (предварительно)
        if project.project_type == "msa":
            self._extract_msa_control_points_raw(project)
        else:
            self._extract_rs10_control_points_raw(project)
        
        # Шаг 3: Извлекаем координаты для таблиц
        self._extract_table_coordinates(project)
        
        # Шаг 4: Извлекаем отклонения
        self._extract_deviations(project)
        
        return project
    
    def _extract_trajectory(self, project: ProjectData):
        """Шаг 1: Извлечение траектории для схемы"""
        if project.project_type == "msa":
            self._extract_msa_trajectory(project)
        else:
            self._extract_rs10_trajectory(project)
    
    def _extract_msa_trajectory(self, project: ProjectData):
        """Извлекает траекторию из MSA проекта (msa_sop.csv)"""
        sop_path = os.path.join(project.path, "msa_sop.csv")
        pop_path = os.path.join(project.path, "project.pop")
        
        if not os.path.exists(sop_path):
            return
        
        try:
            df = pd.read_csv(sop_path)
            
            # Извлекаем координаты
            x = df['x'].values if 'x' in df.columns else np.array([])
            y = df['y'].values if 'y' in df.columns else np.array([])
            z = df['z'].values if 'z' in df.columns else np.zeros_like(x)
            names = df['scanPosName'].values if 'scanPosName' in df.columns else []
            
            # Загружаем матрицу трансформации
            transform_matrix = None
            if os.path.exists(pop_path):
                try:
                    import json
                    with open(pop_path, 'r', encoding='utf-8') as f:
                        pop_data = json.load(f)
                    if '4x4' in pop_data:
                        transform_matrix = np.array(pop_data['4x4'], dtype=np.float64)
                except:
                    pass
            
            # Применяем трансформацию
            if transform_matrix is not None and len(x) > 0:
                coords = np.column_stack([x, y, z])
                transformed = self.converter.apply_transform(coords, transform_matrix)
                x, y, z = transformed[:, 0], transformed[:, 1], transformed[:, 2]
            
            # Для одиночного проекта весь массив представляет собой один сегмент
            trajectory_segment = [(0, len(x))] if len(x) > 0 else []
            
            project.trajectory = TrajectoryData(
                x=x, y=y, z=z,
                names=list(names) if len(names) > 0 else [],
                trajectory_segments=trajectory_segment,
                transform_matrix=transform_matrix,
                source_file="msa_sop.csv",
                project_name=project.name
            )
            project.total_stations = len(x)
            
        except Exception as e:
            print(f"Ошибка извлечения траектории MSA: {e}")
    
    def _extract_rs10_trajectory(self, project: ProjectData):
        """Извлекает траекторию из RS10 проекта (slam_trajectory.txt)"""
        traj_path = os.path.join(project.path, "AUTOSOLVE", "Scanner1", "slam_trajectory.txt")
        
        if not os.path.exists(traj_path):
            return
        
        try:
            # Читаем файл построчно, так как формат сложный
            x_coords = []
            y_coords = []
            z_coords = []
            
            with open(traj_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:  # Минимум timestamp + x, y, z
                        try:
                            # Координаты находятся в колонках 2, 3, 4 (индексы 1, 2, 3)
                            x = float(parts[1])
                            y = float(parts[2])
                            z = float(parts[3])
                            
                            x_coords.append(x)
                            y_coords.append(y)
                            z_coords.append(z)
                        except (ValueError, IndexError):
                            continue
            
            if not x_coords:
                print(f"Не удалось извлечь координаты из {traj_path}")
                return
            
            x = np.array(x_coords)
            y = np.array(y_coords)
            z = np.array(z_coords)
            
            # Используем встроенную матрицу трансформации
            transform_matrix = np.array(MGGT_TO_WGS84_MATRIX, dtype=np.float64)
            
            # Применяем трансформацию
            if len(x) > 0:
                coords = np.column_stack([x, y, z])
                transformed = self.converter.apply_transform(coords, transform_matrix)
                x, y, z = transformed[:, 0], transformed[:, 1], transformed[:, 2]
            
            # Для одиночного проекта весь массив представляет собой один сегмент
            trajectory_segment = [(0, len(x))] if len(x) > 0 else []
            
            project.trajectory = TrajectoryData(
                x=x, y=y, z=z,
                names=[f"Point_{i}" for i in range(len(x))],
                trajectory_segments=trajectory_segment,
                transform_matrix=transform_matrix,
                source_file="slam_trajectory.txt",
                project_name=project.name
            )
            
            # Вычисляем длину траектории
            if len(x) > 1:
                dx = np.diff(x)
                dy = np.diff(y)
                dz = np.diff(z)
                distances = np.sqrt(dx**2 + dy**2 + dz**2)
                project.total_trajectory_length = float(np.sum(distances))
            else:
                project.total_trajectory_length = 0.0
            
            print(f"Загружено {len(x)} точек траектории из RS10 проекта")
            
        except Exception as e:
            print(f"Ошибка извлечения траектории RS10: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_msa_control_points_raw(self, project: ProjectData):
        """
        Извлекает точки из MSA проекта (control_points.csv) без разделения на опорные/контрольные
        Просто загружает все точки, флаг is_gcp будет установлен позже алгоритмом выбора
        """
        cp_path = os.path.join(project.path, "control_points.csv")
        pop_path = os.path.join(project.path, "project.pop")
        
        if not os.path.exists(cp_path):
            return
        
        try:
            df = pd.read_csv(cp_path)
            
            # Загружаем матрицу трансформации
            transform_matrix = None
            if os.path.exists(pop_path):
                try:
                    import json
                    with open(pop_path, 'r', encoding='utf-8') as f:
                        pop_data = json.load(f)
                    if '4x4' in pop_data:
                        transform_matrix = np.array(pop_data['4x4'], dtype=np.float64)
                except:
                    pass
            
            points_list = []
            for idx, row in df.iterrows():
                name = str(row['name']).strip() if 'name' in row else f"Point_{idx}"  # Убираем пробелы
                x = round(float(row['x']), 3) if 'x' in row else 0.0
                y = round(float(row['y']), 3) if 'y' in row else 0.0
                z = round(float(row['z']), 3) if 'z' in row else 0.0
                
                # Сохраняем原始ные координаты для таблиц
                point = ControlPoint(
                    name=name, x=x, y=y, z=z,
                    is_gcp=False,  # Временное значение, будет установлено позже
                    project_name=project.name
                )
                # Отмечаем, что флаг is_gcp еще не установлен из отчета
                point._is_gcp_set_from_report = False
                
                # Сохраняем координаты для таблиц (исходные)
                point.x_table = x
                point.y_table = y
                point.z_table = z
                
                # Координаты для схемы (после трансформации)
                if transform_matrix is not None:
                    coords = np.array([[x, y, z]])
                    transformed = self.converter.apply_transform(coords, transform_matrix)
                    point.x_map, point.y_map, point.z_map = transformed[0]
                else:
                    point.x_map, point.y_map, point.z_map = x, y, z
                
                points_list.append(point)
            
            project.control_points = points_list
            print(f"Загружено {len(points_list)} точек из {cp_path}")
            
        except Exception as e:
            print(f"Ошибка извлечения точек MSA: {e}")
    
    def _extract_rs10_control_points_raw(self, project: ProjectData):
        """
        Извлекает точки из RS10 проекта (SLAM_Refine_Report.csv) без разделения
        """
        report_path = os.path.join(project.path, "AUTOSOLVE", "TGCPReport", "SLAM_Refine_Report.csv")
        
        if not os.path.exists(report_path):
            return
        
        try:
            df = pd.read_csv(report_path, skiprows=1)
            columns = df.columns.tolist()
            
            if len(columns) < 5:
                return
            
            name_col = columns[0]
            x_col = columns[2]
            y_col = columns[3]
            z_col = columns[4]
            
            # Очищаем данные
            df = df.dropna(subset=[name_col])
            df = df[df[name_col] != '']
            df = df[~df[name_col].astype(str).str.contains('Мин|Макс|Среднее|Ср', na=False)]
            
            transform_matrix = np.array(MGGT_TO_WGS84_MATRIX, dtype=np.float64)
            points_list = []
            
            for idx, row in df.iterrows():
                try:
                    name = str(row[name_col])
                    x = round(float(row[x_col]), 3)
                    y = round(float(row[y_col]), 3)
                    z = round(float(row[z_col]), 3)
                    
                    point = ControlPoint(
                        name=name, x=x, y=y, z=z,
                        is_gcp=False,  # Временное значение
                        project_name=project.name
                    )
                    
                    # Координаты для схемы
                    coords = np.array([[x, y, z]])
                    transformed = self.converter.apply_transform(coords, transform_matrix)
                    point.x_map, point.y_map, point.z_map = transformed[0]
                    
                    points_list.append(point)
                    
                except (ValueError, TypeError):
                    continue
            
            project.control_points = points_list
            
        except Exception as e:
            print(f"Ошибка извлечения точек RS10: {e}")
    
    def _extract_coordinates_from_table(self, soup, header_text):
        """
        Извлекает координаты точек из таблицы по заголовку
        Возвращает словарь {имя: (x, y, z)} с нормализованными именами
        Для таблиц 2.4 и 2.5 нужны Easting, Northing, Height (2-4 столбцы)
        """
        coords = {}
        
        # Ищем секцию с нужным заголовком
        header = soup.find(['h2', 'h3', 'h4'], string=re.compile(header_text))
        
        if not header:
            print(f"Заголовок '{header_text}' не найден")
            return coords
        
        # Ищем следующую таблицу после заголовка
        table = header.find_next('table')
        if not table:
            print(f"Таблица после заголовка '{header_text}' не найдена")
            return coords
        
        try:
            # Читаем таблицу с мультииндексными заголовками
            df_list = pd.read_html(StringIO(str(table)), header=[0, 1])
            if not df_list:
                return coords
            df = df_list[0]
            
            print(f"Столбцы таблицы {header_text}: {df.columns.tolist()}")
            
            # Определяем индексы колонок по значениям на уровне 1
            name_col = None
            easting_col = None  # X координата для таблиц
            northing_col = None # Y координата для таблиц
            height_col = None   # Z координата для таблиц
            
            for col_idx, col_name in enumerate(df.columns.get_level_values(1)):
                col_str = str(col_name).lower().strip()
                if 'name' in col_str:
                    name_col = col_idx
                    print(f"Найдена колонка имени: индекс {col_idx}, значение '{col_name}'")
                elif 'easting' in col_str:
                    easting_col = col_idx
                    print(f"Найдена колонка Easting: индекс {col_idx}, значение '{col_name}'")
                elif 'northing' in col_str:
                    northing_col = col_idx
                    print(f"Найдена колонка Northing: индекс {col_idx}, значение '{col_name}'")
                elif 'height' in col_str:
                    height_col = col_idx
                    print(f"Найдена колонка Height: индекс {col_idx}, значение '{col_name}'")
            
            # Проверяем, что все нужные колонки найдены
            if name_col is None:
                print(f"Колонка имени не найдена в таблице {header_text}")
                return coords
            
            if easting_col is None or northing_col is None or height_col is None:
                print(f"Не все координатные колонки найдены: Easting={easting_col}, Northing={northing_col}, Height={height_col}")
                return coords
            
            # Извлекаем данные
            for idx, row in df.iterrows():
                try:
                    name = str(row.iloc[name_col]).strip()
                    if pd.isna(name) or name in ['', 'NaN', 'None', 'nan']:
                        continue
                    
                    # Пропускаем строки с заголовками (если попали)
                    if name.lower() in ['name', 'easting', 'northing', 'height']:
                        continue
                    
                    easting_val = row.iloc[easting_col]
                    northing_val = row.iloc[northing_col]
                    height_val = row.iloc[height_col]
                    
                    # Проверяем, что значения числовые
                    try:
                        easting = round(float(easting_val), 3) if pd.notna(easting_val) else 0.0
                        northing = round(float(northing_val), 3) if pd.notna(northing_val) else 0.0
                        height = round(float(height_val), 3) if pd.notna(height_val) else 0.0
                        
                        coords[name] = (easting, northing, height)
                        print(f"Извлечены координаты для {name}: Easting={easting}, Northing={northing}, Height={height}")
                    except (ValueError, TypeError):
                        print(f"Нечисловые значения для точки {name}: Easting={easting_val}, Northing={northing_val}, Height={height_val}")
                        continue
                        
                except Exception as e:
                    print(f"Ошибка обработки строки {idx}: {e}")
                    continue
        
        except Exception as e:
            print(f"Ошибка парсинга таблицы {header_text}: {e}")
            import traceback
            traceback.print_exc()
            return self._parse_table_manually(table)
        
        return coords

    def _parse_table_manually(self, table):
        """Ручной парсинг таблицы через BeautifulSoup как запасной вариант"""
        coords = {}
        rows = table.find_all('tr')
        if len(rows) < 3:
            return coords
        
        # Определяем заголовки (обычно во второй строке)
        header_row = rows[1] if len(rows) > 1 else rows[0]
        headers = [th.get_text().strip().lower() for th in header_row.find_all(['th', 'td'])]
        
        name_idx = -1
        x_idx = -1
        y_idx = -1
        z_idx = -1
        
        for i, h in enumerate(headers):
            if 'name' in h:
                name_idx = i
            elif 'easting' in h or ('x' in h and '[' in h):
                x_idx = i
            elif 'northing' in h or ('y' in h and '[' in h):
                y_idx = i
            elif 'height' in h or ('z' in h and '[' in h):
                z_idx = i
        
        if name_idx == -1 or x_idx == -1 or y_idx == -1 or z_idx == -1:
            return coords
        
        # Парсим строки данных (начиная с 2)
        for i in range(2, len(rows)):
            row = rows[i]
            cells = row.find_all('td')
            if len(cells) <= max(name_idx, x_idx, y_idx, z_idx):
                continue
            
            try:
                name = cells[name_idx].get_text().strip()
                if not name or name in ['', 'NaN', 'None']:
                    continue
                
                x_text = cells[x_idx].get_text().strip().replace(',', '.')
                y_text = cells[y_idx].get_text().strip().replace(',', '.')
                z_text = cells[z_idx].get_text().strip().replace(',', '.')
                
                x = float(x_text)
                y = float(y_text)
                z = float(z_text)
                
                coords[name] = (x, y, z)
            except:
                continue
        
        return coords
    
    def _extract_table_coordinates(self, project: ProjectData):
        """Шаг 3: Извлечение координат для таблиц"""
        html_path = os.path.join(project.path, "html", "report.html")
        
        if os.path.exists(html_path):
            try:
                from bs4 import BeautifulSoup
                
                with open(html_path, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                
                print("\n=== Извлечение координат из HTML ===")
                
                # Ищем таблицу 2.4 (Control Points)
                print("Поиск таблицы 2.4 Control Points...")
                table_coords = self._extract_coordinates_from_table(soup, "2.4 Control Points")
                print(f"Из таблицы 2.4 извлечено координат: {len(table_coords)}")
                
                # Если есть таблица 2.5, тоже извлекаем
                print("Поиск таблицы 2.5 Check Points...")
                table_coords_check = self._extract_coordinates_from_table(soup, "2.5 Check Points")
                if table_coords_check:
                    print(f"Из таблицы 2.5 извлечено координат: {len(table_coords_check)}")
                    table_coords.update(table_coords_check)
                
                print(f"Всего извлечено координат из HTML: {len(table_coords)}")
                
                # Обновляем координаты для таблиц
                updated_count = 0
                for point in project.control_points:
                    if point.name in table_coords:
                        point.x_table, point.y_table, point.z_table = table_coords[point.name]
                        updated_count += 1
                        print(f"Для точки {point.name} обновлены координаты: X={point.x_table}, Y={point.y_table}, Z={point.z_table}")
                    else:
                        print(f"Точка {point.name} не найдена в HTML, используются исходные координаты")
                
                print(f"Обновлено координат для {updated_count} из {len(project.control_points)} точек")
                
            except Exception as e:
                print(f"Ошибка извлечения координат из HTML: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"HTML отчет не найден: {html_path}, используются исходные координаты")
        
        # Если координаты для таблиц не были обновлены из HTML, используем исходные
        for point in project.control_points:
            if point.x_table is None:
                point.x_table = point.x
                point.y_table = point.y
                point.z_table = point.z
    
    def _extract_deviations(self, project: ProjectData):
        """Шаг 4: Извлечение отклонений"""
        if project.project_type == "msa":
            self._extract_msa_deviations(project)
        else:
            self._extract_rs10_deviations(project)
    
    def _extract_msa_deviations(self, project: ProjectData):
        """Извлекает отклонения из MSA проекта (report.html)"""
        html_path = os.path.join(project.path, "html", "report.html")
        if not os.path.exists(html_path):
            return
        
        try:
            from bs4 import BeautifulSoup
            import re
            from io import StringIO
            
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        
            all_deviations = {}
            
            # Извлекаем из секции 4.4.1
            stats_441, deviations_441 = self._extract_section_deviations(soup, "4.4.1 Control Points", has_force_match=True)
            if deviations_441 is not None:
                for _, row in deviations_441.iterrows():
                    name = str(row['CP_Name']).strip()  # Убираем пробелы
                    dx = round(float(row['dX']), 3)
                    dy = round(float(row['dY']), 3)
                    dz = round(float(row['dZ']), 3)
                    
                    # Вычисляем оба расстояния
                    dist_2d = round(np.sqrt(dx**2 + dy**2), 3)
                    dist_3d = round(np.sqrt(dx**2 + dy**2 + dz**2), 3)
                    
                    all_deviations[name] = (dx, dy, dz, dist_2d, dist_3d)
                    print(f"Из секции 4.4.1 загружена точка {name}")
            
            # Извлекаем из секции 4.4.2
            stats_442, deviations_442 = self._extract_section_deviations(soup, "4.4.2 Check Points", has_force_match=False)
            if deviations_442 is not None:
                for _, row in deviations_442.iterrows():
                    name = str(row['CP_Name']).strip()  # Убираем пробелы
                    dx = round(float(row['dX']), 3)
                    dy = round(float(row['dY']), 3)
                    dz = round(float(row['dZ']), 3)
                    
                    # Вычисляем оба расстояния
                    dist_2d = round(np.sqrt(dx**2 + dy**2), 3)
                    dist_3d = round(np.sqrt(dx**2 + dy**2 + dz**2), 3)
                    
                    all_deviations[name] = (dx, dy, dz, dist_2d, dist_3d)
                    print(f"Из секции 4.4.2 загружена точка {name}")
            
            # Извлекаем отдельно точки из секций 4.4.1 и 4.4.2
            control_points_from_html = set()  # Точки из 4.4.1 (опорные)
            check_points_from_html = set()    # Точки из 4.4.2 (контрольные)
            
            # Извлекаем из секции 4.4.1 (Control Points)
            stats_441, deviations_441 = self._extract_section_deviations(soup, "4.4.1 Control Points", has_force_match=True)
            if deviations_441 is not None:
                for _, row in deviations_441.iterrows():
                    name = str(row['CP_Name']).strip()  # Убираем пробелы
                    dx = round(float(row['dX']), 3)
                    dy = round(float(row['dY']), 3)
                    dz = round(float(row['dZ']), 3)
                    
                    # Вычисляем оба расстояния
                    dist_2d = round(np.sqrt(dx**2 + dy**2), 3)
                    dist_3d = round(np.sqrt(dx**2 + dy**2 + dz**2), 3)
                    
                    all_deviations[name] = (dx, dy, dz, dist_2d, dist_3d)
                    control_points_from_html.add(name)
                    print(f"Из секции 4.4.1 загружена точка {name}")
            
            # Извлекаем из секции 4.4.2 (Check Points)
            stats_442, deviations_442 = self._extract_section_deviations(soup, "4.4.2 Check Points", has_force_match=False)
            if deviations_442 is not None:
                for _, row in deviations_442.iterrows():
                    name = str(row['CP_Name']).strip()  # Убираем пробелы
                    dx = round(float(row['dX']), 3)
                    dy = round(float(row['dY']), 3)
                    dz = round(float(row['dZ']), 3)
                    
                    # Вычисляем оба расстояния
                    dist_2d = round(np.sqrt(dx**2 + dy**2), 3)
                    dist_3d = round(np.sqrt(dx**2 + dy**2 + dz**2), 3)
                    
                    all_deviations[name] = (dx, dy, dz, dist_2d, dist_3d)
                    check_points_from_html.add(name)
                    print(f"Из секции 4.4.2 загружена точка {name}")
            
            # Заполняем отклонения и устанавливаем флаги is_gcp на основе секции, из которой были извлечены данные
            points_with_deviations = 0
            for point in project.control_points:
                point_name = point.name.strip()  # Убираем пробелы из имени точки проекта
                if point_name in all_deviations:
                    dx, dy, dz, dist_2d, dist_3d = all_deviations[point_name]
                    point.dx = round(dx, 3) if dx is not None else dx
                    point.dy = round(dy, 3) if dy is not None else dy
                    point.dz = round(dz, 3) if dz is not None else dz
                    point.dist_2d = round(dist_2d, 3) if dist_2d is not None else dist_2d
                    point.dist_3d = round(dist_3d, 3) if dist_3d is not None else dist_3d
                    points_with_deviations += 1
                    print(f"Сопоставлена точка: {point.name} -> {point_name}")
                    
                    # Устанавливаем флаг is_gcp на основе секции, из которой были извлечены отклонения
                    if point_name in control_points_from_html:
                        point.is_gcp = True  # Это опорная точка (из 4.4.1)
                        point._is_gcp_set_from_report = True
                    elif point_name in check_points_from_html:
                        point.is_gcp = False  # Это контрольная точка (из 4.4.2)
                        point._is_gcp_set_from_report = True
                else:
                    print(f"Предупреждение: для точки '{point.name}' (нормализовано: '{point_name}') нет отклонений")
            
            print(f"Загружено отклонений для {points_with_deviations} из {len(project.control_points)} точек")
            
        except Exception as e:
            print(f"Ошибка извлечения отклонений MSA: {e}")
            import traceback
            traceback.print_exc()

    def _extract_section_deviations(self, soup, section_title, has_force_match=True):
        """Извлекает статистику и отклонения из секции (4.4.1 или 4.4.2)"""
        # Ищем секцию
        section = None
        for s in soup.find_all('section'):
            header = s.find(['h3'])
            if header and section_title in header.get_text():
                section = s
                break
        
        if not section:
            header = soup.find(['h3'], string=re.compile(section_title))
            if header:
                section = header.find_parent('section')
        
        if not section:
            return None, None
        
        tables = section.find_all('table')
        if len(tables) < 2:
            return None, None
        
        # Парсим статистику (первая таблица)
        stats_df = self._parse_stats_table(tables[0])
        
        # Парсим отклонения (вторая таблица)
        deviations_df = self._parse_deviations_table_new(tables[1], has_force_match)
        
        return stats_df, deviations_df

    def _parse_stats_table(self, table):
        """Парсит таблицу со статистикой"""
        try:
            data = []
            rows = table.find_all('tr')
            for row in rows[1:]:  # Пропускаем заголовок
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 5:
                    row_data = []
                    for col in cols[:5]:
                        text = col.get_text().strip().replace('\xa0', ' ').replace('---', 'NaN')
                        row_data.append(text)
                    if row_data:
                        data.append(row_data)
        
            if data:
                df = pd.DataFrame(data, columns=['Метрика', 'dX', 'dY', 'dZ', 'dist'])
                for col in ['dX', 'dY', 'dZ', 'dist']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
            return None
        except Exception as e:
            print(f"Ошибка парсинга статистики: {e}")
            return None

    def _parse_deviations_table_new(self, table, has_force_match=True):
        """Парсит таблицу с отклонениями по точкам"""
        try:
            data = []
            rows = table.find_all('tr')
            
            # Определяем заголовки (обычно во второй строке)
            if len(rows) > 1:
                header_row = rows[1]
            else:
                header_row = rows[0]
        
            headers = [th.get_text().strip().lower() for th in header_row.find_all(['th'])]
            
            # Парсим данные (начиная с 2)
            for i in range(2, len(rows)):
                row = rows[i]
                cells = row.find_all('td')
                
                # Пропускаем пустые строки-разделители
                if len(cells) == 0 or (len(cells) == 1 and cells[0].get_text().strip() == ''):
                    continue
                
                if len(cells) >= 7:
                    try:
                        row_data = [c.get_text().strip() for c in cells]
                        
                        data_row = {
                            'CP_Name': row_data[0] if len(row_data) > 0 else '',
                            'Scan_Position': row_data[1] if len(row_data) > 1 else '',
                            'Name': row_data[2] if len(row_data) > 2 else '',
                            'dX': round(float(row_data[3]), 3) if len(row_data) > 3 and row_data[3] and row_data[3] != '' else None,
                            'dY': round(float(row_data[4]), 3) if len(row_data) > 4 and row_data[4] and row_data[4] != '' else None,
                            'dZ': round(float(row_data[5]), 3) if len(row_data) > 5 and row_data[5] and row_data[5] != '' else None,
                            'dist': round(float(row_data[6]), 3) if len(row_data) > 6 and row_data[6] and row_data[6] != '' else None
                        }
                        
                        if has_force_match and len(row_data) > 7:
                            data_row['Force_match'] = row_data[7]
                        
                        if any(v is not None for v in [data_row['dX'], data_row['dY'], data_row['dZ']]):
                            data.append(data_row)
                    except Exception as e:
                        continue
        
            if data:
                return pd.DataFrame(data)
            return None
        except Exception as e:
            print(f"Ошибка парсинга таблицы отклонений: {e}")
            return None

    
    def _extract_rs10_deviations(self, project: ProjectData):
        """Извлекает отклонения из RS10 проекта (SLAM_Refine_Report.csv)"""
        report_path = os.path.join(project.path, "AUTOSOLVE", "TGCPReport", "SLAM_Refine_Report.csv")
        
        if not os.path.exists(report_path):
            return
        
        try:
            df = pd.read_csv(report_path, skiprows=1)
            columns = df.columns.tolist()
            
            if len(columns) < 11:
                return
            
            name_col = columns[0]
            dx_col = columns[8]
            dy_col = columns[9]
            dz_col = columns[10]
            
            df = df.dropna(subset=[name_col])
            df = df[df[name_col] != '']
            df = df[~df[name_col].astype(str).str.contains('Мин|Макс|Среднее|Ср', na=False)]
            
            # Создаем словарь отклонений для ВСЕХ точек
            deviations = {}
            for idx, row in df.iterrows():
                try:
                    name = str(row[name_col])
                    dx = float(row[dx_col]) if pd.notna(row[dx_col]) else None
                    dy = float(row[dy_col]) if pd.notna(row[dy_col]) else None
                    dz = float(row[dz_col]) if pd.notna(row[dz_col]) else None
                    
                    if dx is not None and dy is not None and dz is not None:
                        dist_2d = round(np.sqrt(dx**2 + dy**2), 3)
                        dist_3d = round(np.sqrt(dx**2 + dy**2 + dz**2), 3)
                        deviations[name] = (round(dx, 3), round(dy, 3), round(dz, 3), dist_2d, dist_3d)
                except (ValueError, TypeError):
                    continue
            
            # Заполняем отклонения для ВСЕХ точек проекта
            points_with_deviations = 0
            for point in project.control_points:
                if point.name in deviations:
                    dx, dy, dz, dist_2d, dist_3d = deviations[point.name]
                    point.dx = dx
                    point.dy = dy
                    point.dz = dz
                    point.dist_2d = dist_2d
                    point.dist_3d = dist_3d
                    points_with_deviations += 1
            
            print(f"RS10: загружены отклонения для {points_with_deviations} из {len(project.control_points)} точек")
            
        except Exception as e:
            print(f"Ошибка извлечения отклонений RS10: {e}")
    
    def _parse_msa_deviations_section(self, section):
        """
        Парсит секцию 4.4.1 или 4.4.2 и извлекает отклонения из таблицы с детальными данными
        Учитывает структуру из примера 441442.txt
        """
        deviations = {}
        
        # Находим все таблицы в секции
        tables = section.find_all('table')
        if len(tables) < 2:
            return deviations
        
        # Вторая таблица (индекс 1) содержит детальные отклонения
        detailed_table = tables[1]
        
        rows = detailed_table.find_all('tr')
        if len(rows) < 3:  # Должны быть заголовки + данные
            return deviations
        
        # Определяем индексы колонок по заголовкам
        header_row = rows[1] if len(rows) > 1 else rows[0]
        headers = [th.get_text().strip().lower() for th in header_row.find_all(['th', 'td'])]
        
        name_idx = -1
        dx_idx = -1
        dy_idx = -1
        dz_idx = -1
        dist_idx = -1
        
        for i, h in enumerate(headers):
            if 'cp name' in h or 'name' in h:
                name_idx = i
            elif 'dx' in h:
                dx_idx = i
            elif 'dy' in h:
                dy_idx = i
            elif 'dz' in h:
                dz_idx = i
            elif 'dist' in h:
                dist_idx = i
        
        if name_idx == -1 or dx_idx == -1 or dy_idx == -1 or dz_idx == -1 or dist_idx == -1:
            print(f"Не найдены все необходимые колонки в таблице отклонений")
            return deviations
        
        # Парсим строки данных (начиная с 2, чтобы пропустить заголовки)
        for i in range(2, len(rows)):
            row = rows[i]
            cells = row.find_all('td')
            
            # Пропускаем пустые строки-разделители
            if len(cells) == 0 or (len(cells) == 1 and cells[0].get_text().strip() == ''):
                continue
            
            if len(cells) <= max(name_idx, dx_idx, dy_idx, dz_idx, dist_idx):
                continue
            
            try:
                name = cells[name_idx].get_text().strip()
                if not name or name in ['', 'NaN', 'None']:
                    continue
                
                dx_text = cells[dx_idx].get_text().strip()
                dy_text = cells[dy_idx].get_text().strip()
                dz_text = cells[dz_idx].get_text().strip()
                dist_text = cells[dist_idx].get_text().strip()
                
                dx = round(float(dx_text.replace(',', '.')), 3)
                dy = round(float(dy_text.replace(',', '.')), 3)
                dz = round(float(dz_text.replace(',', '.')), 3)
                dist = round(float(dist_text.replace(',', '.')), 3)
                
                deviations[name] = (dx, dy, dz, dist)
                print(f"Извлечены отклонения для {name}: dX={dx}, dY={dy}, dZ={dz}, dist={dist}")
                
            except (ValueError, IndexError) as e:
                print(f"Ошибка парсинга отклонений в строке: {e}")
                continue
        
        return deviations
    
    def _parse_deviations_table_enhanced(self, table):
        """
        Улучшенный парсинг таблицы отклонений, возвращает словарь {имя: (dx, dy, dz, dist)}
        """
        rows = table.find_all('tr')
        deviations = {}
        
        for i in range(2, len(rows)):  # Пропускаем заголовки
            row = rows[i]
            cols = row.find_all('td')
            if len(cols) >= 7:
                try:
                    name = cols[0].get_text().strip()
                    if name and name not in ['', 'NaN', 'None']:
                        dx = float(cols[3].get_text().strip())
                        dy = round(float(cols[4].get_text().strip()), 3)
                        dz = round(float(cols[5].get_text().strip()), 3)
                        dist = round(float(cols[6].get_text().strip()), 3)
                        deviations[name] = (dx, dy, dz, dist)
                except (ValueError, IndexError) as e:
                    continue
        
        return deviations
    
    def _parse_deviations_table(self, table, project: ProjectData, is_control: bool):
        """Парсит таблицу отклонений из HTML"""
        rows = table.find_all('tr')
        
        for i in range(2, len(rows)):  # Пропускаем заголовки
            row = rows[i]
            cols = row.find_all('td')
            if len(cols) >= 7:
                try:
                    name = cols[0].get_text().strip()
                    dx = float(cols[3].get_text().strip())
                    dy = round(float(cols[4].get_text().strip()), 3)
                    dz = round(float(cols[5].get_text().strip()), 3)
                    dist = round(float(cols[6].get_text().strip()), 3)
                    
                    # Находим точку с таким именем
                    for point in project.control_points:
                        if point.name == name:
                            point.dx = dx
                            point.dy = dy
                            point.dz = dz
                            point.dist = dist
                            break
                except (ValueError, IndexError):
                    continue
    
    def finalize_point_selection(self, projects: List[ProjectData],
                                project_type: str) -> List[ControlPoint]:
       """
       Финальный шаг: применяет алгоритм выбора опорных/контрольных точек
       Вызывается после загрузки всех данных
       """
       # Проверяем, есть ли уже установленные флаги из отчета (например, из report.html)
       has_report_flags = False
       for project in projects:
           for point in project.control_points:
               if point._report_marked_as_gcp or point._report_marked_as_check:
                   has_report_flags = True
                   break
           if has_report_flags:
               break
       
       # Проверяем, есть ли точки, у которых флаг is_gcp был установлен из отчета
       has_report_flags = False
       for project in projects:
           for point in project.control_points:
               if point._is_gcp_set_from_report:
                   has_report_flags = True
                   break
           if has_report_flags:
               break
       
       if has_report_flags:
           # Если флаги уже установлены из отчета, не пересчитываем их
           all_points = []
           for project in projects:
               all_points.extend(project.control_points)
           print(f"Используем предопределенные флаги точек из отчета: опорных - {len([p for p in all_points if p.is_gcp])}, контрольных - {len([p for p in all_points if not p.is_gcp])}")
       else:
           # Применяем алгоритм выбора только если флаги не были установлены из отчета
           all_points = self.selector.select_points(projects, project_type)
           
           # Выводим информацию о распределении
           gcps = [p for p in all_points if p.is_gcp]
           checks = [p for p in all_points if not p.is_gcp]
           print(f"Алгоритм выбора: опорных точек - {len(gcps)}, контрольных - {len(checks)}")
       
       return all_points
    
    def combine_projects(self, projects: List[ProjectData]) -> ProjectData:
        """
        Объединяет данные нескольких проектов для мультивыбора
        """
        if not projects:
            return ProjectData(name="Empty", path="", project_type="msa")
        
        if len(projects) == 1:
            return projects[0]
        
        combined = ProjectData(
            name="Combined",
            path="",
            project_type=projects[0].project_type
        )
        
        # Объединяем траектории
        all_x, all_y, all_z, all_names = [], [], [], []
        trajectory_segments = []
        current_index = 0
        
        for p in projects:
            segment_start = current_index
            segment_end = current_index + len(p.trajectory.x)
            trajectory_segments.append((segment_start, segment_end))
            
            all_x.extend(p.trajectory.x)
            all_y.extend(p.trajectory.y)
            all_z.extend(p.trajectory.z)
            all_names.extend(p.trajectory.names)
            
            current_index = segment_end
        
        combined.trajectory = TrajectoryData(
            x=np.array(all_x), y=np.array(all_y), z=np.array(all_z),
            names=all_names,
            trajectory_segments=trajectory_segments,
            project_name="Combined"
        )
        
        # Объединяем точки (флаги is_gcp уже должны быть установлены)
        all_points = []
        for p in projects:
            all_points.extend(p.control_points)
        combined.control_points = all_points
        
        # Общая статистика
        combined.total_stations = sum(p.total_stations for p in projects)
        combined.total_trajectory_length = sum(p.total_trajectory_length for p in projects)
        
        return combined