"""
Модуль с моделями данных для хранения всей информации о проектах.
Содержит каталоги точек и значений, необходимых для генерации отчетов.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd


@dataclass
class TrajectoryData:
    """Данные траектории для схемы (из msa_sop.csv или slam_trajectory.txt)"""

    x: np.ndarray = field(default_factory=lambda: np.array([]))
    y: np.ndarray = field(default_factory=lambda: np.array([]))
    z: np.ndarray = field(default_factory=lambda: np.array([]))
    names: List[str] = field(default_factory=list)
    trajectory_segments: List[Tuple[int, int]] = field(
        default_factory=list
    )  # Список кортежей (start_index, end_index) для отдельных сегментов траектории
    transform_matrix: Optional[np.ndarray] = None
    source_file: str = ""
    project_name: str = ""


@dataclass
class ControlPoint:
    """Точка (опорная или контрольная)"""

    name: str
    x: float
    y: float
    z: float
    is_gcp: bool  # True - опорная, False - контрольная
    project_name: str = ""

    # Для таблиц (из report.html или SLAM_Refine_Report.csv)
    x_table: Optional[float] = None
    y_table: Optional[float] = None
    z_table: Optional[float] = None

    # Для схемы (после трансформации)
    x_map: Optional[float] = None
    y_map: Optional[float] = None
    z_map: Optional[float] = None

    # Для отклонений (из раздела 4.4)
    dx: Optional[float] = None
    dy: Optional[float] = None
    dz: Optional[float] = None
    dist: Optional[float] = None  # Устаревшее поле, сохраняем для совместимости
    dist_2d: Optional[float] = None  # Плановое отклонение √(dx² + dy²)
    dist_3d: Optional[float] = None  # Пространственное отклонение √(dx² + dy² + dz²)

    # Временные поля для внутреннего использования
    _report_marked_as_gcp: bool = False
    _report_marked_as_check: bool = False
    _is_gcp_set_from_report: bool = False


@dataclass
class StatisticsData:
    """Статистические данные для опорных и контрольных точек"""

    # Для опорных точек (control points)
    control_min_dx: float = 0.0
    control_min_dy: float = 0.0
    control_min_dz: float = 0.0
    control_min_2d: float = 0.0
    control_min_3d: float = 0.0

    control_max_dx: float = 0.0
    control_max_dy: float = 0.0
    control_max_dz: float = 0.0
    control_max_2d: float = 0.0
    control_max_3d: float = 0.0

    control_mean_dx: float = 0.0
    control_mean_dy: float = 0.0
    control_mean_dz: float = 0.0
    control_mean_2d: float = 0.0
    control_mean_3d: float = 0.0

    control_std_dx: float = 0.0
    control_std_dy: float = 0.0
    control_std_dz: float = 0.0
    control_std_2d: float = 0.0
    control_std_3d: float = 0.0

    control_mad_dx: float = 0.0
    control_mad_dy: float = 0.0
    control_mad_dz: float = 0.0
    control_mad_2d: float = 0.0
    control_mad_3d: float = 0.0

    # Для контрольных точек (check points)
    check_min_dx: float = 0.0
    check_min_dy: float = 0.0
    check_min_dz: float = 0.0
    check_min_2d: float = 0.0
    check_min_3d: float = 0.0

    check_max_dx: float = 0.0
    check_max_dy: float = 0.0
    check_max_dz: float = 0.0
    check_max_2d: float = 0.0
    check_max_3d: float = 0.0

    check_mean_dx: float = 0.0
    check_mean_dy: float = 0.0
    check_mean_dz: float = 0.0
    check_mean_2d: float = 0.0
    check_mean_3d: float = 0.0

    check_std_dx: float = 0.0
    check_std_dy: float = 0.0
    check_std_dz: float = 0.0
    check_std_2d: float = 0.0
    check_std_3d: float = 0.0

    check_mad_dx: float = 0.0
    check_mad_dy: float = 0.0
    check_mad_dz: float = 0.0
    check_mad_2d: float = 0.0
    check_mad_3d: float = 0.0

    def to_dataframe_control(self) -> pd.DataFrame:
        """Преобразует статистику опорных точек в DataFrame"""
        data = {
            "Метрика": ["Min", "Max", "Mean", "Std Dev", "MAD"],
            "dX": [
                self.control_min_dx,
                self.control_max_dx,
                self.control_mean_dx,
                self.control_std_dx,
                self.control_mad_dx,
            ],
            "dY": [
                self.control_min_dy,
                self.control_max_dy,
                self.control_mean_dy,
                self.control_std_dy,
                self.control_mad_dy,
            ],
            "dZ": [
                self.control_min_dz,
                self.control_max_dz,
                self.control_mean_dz,
                self.control_std_dz,
                self.control_mad_dz,
            ],
            "2D_dist": [
                self.control_min_2d,
                self.control_max_2d,
                self.control_mean_2d,
                self.control_std_2d,
                self.control_mad_2d,
            ],
            "3D_dist": [
                self.control_min_3d,
                self.control_max_3d,
                self.control_mean_3d,
                self.control_std_3d,
                self.control_mad_3d,
            ],
        }
        return pd.DataFrame(data)

    def to_dataframe_check(self) -> pd.DataFrame:
        """Преобразует статистику контрольных точек в DataFrame"""
        data = {
            "Метрика": ["Min", "Max", "Mean", "Std Dev", "MAD"],
            "dX": [
                self.check_min_dx,
                self.check_max_dx,
                self.check_mean_dx,
                self.check_std_dx,
                self.check_mad_dx,
            ],
            "dY": [
                self.check_min_dy,
                self.check_max_dy,
                self.check_mean_dy,
                self.check_std_dy,
                self.check_mad_dy,
            ],
            "dZ": [
                self.check_min_dz,
                self.check_max_dz,
                self.check_mean_dz,
                self.check_std_dz,
                self.check_mad_dz,
            ],
            "2D_dist": [
                self.check_min_2d,
                self.check_max_2d,
                self.check_mean_2d,
                self.check_std_2d,
                self.check_mad_2d,
            ],
            "3D_dist": [
                self.check_min_3d,
                self.check_max_3d,
                self.check_mean_3d,
                self.check_std_3d,
                self.check_mad_3d,
            ],
        }
        return pd.DataFrame(data)


@dataclass
class ProjectData:
    """Данные одного проекта"""

    name: str
    path: str
    project_type: str  # 'msa' или 'rs10'

    # Данные для схемы
    trajectory: TrajectoryData = field(default_factory=TrajectoryData)

    # Опорные и контрольные точки
    control_points: List[ControlPoint] = field(default_factory=list)

    # Статистика
    statistics: StatisticsData = field(default_factory=StatisticsData)

    # Временные файлы (пути к сгенерированным изображениям)
    map_image_path: Optional[str] = None
    control_graph_path: Optional[str] = None
    check_graph_path: Optional[str] = None

    # Информация о карте
    used_osm_map: bool = False

    # Общая статистика
    total_trajectory_length: float = 0.0
    total_stations: int = 0

    # Информация о структуре HTML отчета (только для MSA)
    html_structure_status: str = (
        "unknown"  # 'full', 'partial', 'minimal', 'invalid', 'no_html', 'error'
    )
    has_check_points_in_report: bool = False
    user_choice_for_incomplete: Optional[str] = (
        None  # 'skip_checks', 'algorithm', 'cancel'
    )

    def get_gcps(self) -> List[ControlPoint]:
        """Возвращает опорные точки"""
        return [p for p in self.control_points if p.is_gcp]

    def get_checkpoints(self) -> List[ControlPoint]:
        """Возвращает контрольные точки"""
        return [p for p in self.control_points if not p.is_gcp]

    @property
    def gcp_count(self) -> int:
        return len(self.get_gcps())

    @property
    def checkpoint_count(self) -> int:
        return len(self.get_checkpoints())


@dataclass
class ReportData:
    """Общие данные для отчета (может объединять несколько проектов)"""

    projects: List[ProjectData] = field(default_factory=list)

    # Объединенные данные для мультивыбора
    combined_trajectory: TrajectoryData = field(default_factory=TrajectoryData)
    combined_control_points: List[ControlPoint] = field(default_factory=list)
    combined_statistics: StatisticsData = field(default_factory=StatisticsData)

    # Флаги
    is_multi_project: bool = False

    def add_project(self, project: ProjectData):
        self.projects.append(project)
        self.is_multi_project = len(self.projects) > 1

    @property
    def total_gcps(self) -> int:
        return sum(p.gcp_count for p in self.projects)

    @property
    def total_checkpoints(self) -> int:
        return sum(p.checkpoint_count for p in self.projects)

    @property
    def total_stations(self) -> int:
        return sum(p.total_stations for p in self.projects)

    @property
    def total_trajectory_length(self) -> float:
        return sum(p.total_trajectory_length for p in self.projects)
