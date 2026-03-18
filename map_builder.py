"""
Модуль для построения схемы расположения точек (шаг 7).
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pyproj
import tempfile
import os
import math
import requests
from PIL import Image
import concurrent.futures
from typing import Optional

from data_models import ProjectData, ControlPoint
from utils import CoordinateConverter
from constants import MAP_COLORS

# Константы для OSM тайлов
tileSize = 256
servers = ["tile.openstreetmap.org"]
server_protocol = "https"
user_agent = "RIEGL_osmtiles"
cacheDir = os.path.join(tempfile.gettempdir(), "osmtiles_cache")


def deg2tile(lat_deg, lon_deg, zoom):
    """Calculate tile index for coordinate and zoom level."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    return (xtile, ytile)


def tile2deg(xtile, ytile, zoom):
    """Transform tile position to coordinate."""
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)


def _downloadTile(zoom, x, y, timeout=2):
    """Download a single tile from OSM."""
    imageData = None
    lastError = None
    for attempt in range(3):
        server = servers[attempt % len(servers)]
        url = server_protocol + "://" + server + "/{0}/{1}/{2}.png".format(zoom, x, y)
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": user_agent})
            if r.status_code == 200:
                imageData = r.content
                break
            else:
                lastError = RuntimeError(
                    "OSM tile download request returned status code {}".format(r.status_code))
        except Exception as err:
            lastError = err
    if imageData is None:
        if lastError is not None:
            raise lastError
        else:
            raise RuntimeError("Download of OSM tile failed.")
    return imageData


def downloadTiles(zoom, tiles, timeout=2):
    """Download multiple tiles concurrently."""
    # Создаем кэш директорию если её нет
    if not os.path.exists(cacheDir):
        os.makedirs(cacheDir, exist_ok=True)
    
    neededTiles = []
    for x, y in tiles:
        filepath = os.path.join(cacheDir, "{0}_{1}_{2}.png".format(zoom, x, y))
        if not os.path.exists(filepath):
            neededTiles.append((x, y))
    
    if not neededTiles:
        return
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_images = {executor.submit(_downloadTile, zoom, x, y, timeout): (x, y) for x, y in neededTiles}
        for future in concurrent.futures.as_completed(future_to_images):
            x, y = future_to_images[future]
            filepath = os.path.join(cacheDir, "{0}_{1}_{2}.png".format(zoom, x, y))
            imgData = future.result()
            with open(filepath, "wb") as f:
                f.write(imgData)


class StaticMap:
    """Класс для создания статической карты из тайлов OSM."""
    
    def __init__(self, imgSize=(400, 400), imgPadding=(16, 16)):
        self._imgSize = imgSize
        self._imgPadding = imgPadding
        self._markers = []
        self._zoomLevel = 0
        self.downloadTimeout = 2.0

    def addMarker(self, lat, lon):
        self._markers.append({'lat': lat, 'lon': lon})

    @property
    def zoomLevel(self):
        return self._zoomLevel

    def createMap(self, maxZoom=18):
        # Создаем кэш директорию
        if not os.path.exists(cacheDir):
            os.makedirs(cacheDir, exist_ok=True)

        # Вычисляем необходимые тайлы
        aabb = self._calcMarkerAABB()  # (lat, lon, w, h)
        zoom = self._calcZoomLevel(aabb[0], aabb[1], aabb[2], aabb[3], maxZoom=maxZoom)
        zoom = min(zoom, maxZoom)
        self._zoomLevel = zoom
        
        cx, cy = deg2tile(aabb[0], aabb[1], zoom)
        w, h = self._imgSize
        top = cy - h * 0.5 / tileSize
        bottom = cy + h * 0.5 / tileSize
        left = cx - w * 0.5 / tileSize
        right = cx + w * 0.5 / tileSize
        
        tx0 = math.floor(left)
        ty0 = math.floor(top)
        tw = int(math.ceil(right) - math.floor(left))
        th = int(math.ceil(bottom) - math.floor(top))
        
        tiles = []
        for i in range(tw):
            for j in range(th):
                tiles.append((tx0 + i, ty0 + j))

        downloadTiles(zoom, tiles, timeout=self.downloadTimeout)

        image = Image.new('RGBA', self._imgSize, "#ffff")
        self._drawMap(image, zoom, tiles, top, left)
        return image

    def _calcMarkerAABB(self):
        """Calculate marker bounding box in degrees."""
        latitudes = [m['lat'] for m in self._markers]
        longitudes = [m['lon'] for m in self._markers]
        
        if not latitudes or not longitudes:
            return (0, 0, 0, 0)
        
        lat_min = min(latitudes)
        lat_max = max(latitudes)
        lon_min = min(longitudes)
        lon_max = max(longitudes)
        
        w = lon_max - lon_min
        h = lat_max - lat_min
        
        return (lat_min + h * 0.5, lon_min + w * 0.5, w, h)

    def _calcZoomLevel(self, lat, lon, w, h, maxZoom=18):
        """Calculate zoom level so that all markers fit into the output image."""
        imgWidth, imgHeight = self._imgSize
        padLeft, padTop = self._imgPadding
        zoom = maxZoom
        x_range = 2 * 180.0
        y_range = 2 * math.degrees(math.atan(math.sinh(math.pi)))
        y_range = y_range / math.cos(math.radians(lat))
        
        while zoom > 0:
            n = 2.0 ** zoom
            lon_pixels = tileSize * n / x_range * w
            lat_pixels = tileSize * n / y_range * h
            if (lon_pixels + padLeft < imgWidth) and (lat_pixels + padTop < imgHeight):
                break
            zoom -= 1
        return zoom

    def _drawMap(self, image, zoom, tiles, top, left):
        """Compose tiles into output image."""
        for x, y in tiles:
            filepath = os.path.join(cacheDir, "{0}_{1}_{2}.png".format(zoom, x, y))
            if os.path.exists(filepath):
                img = Image.open(filepath)
                box = (
                    int((x - left) * tileSize),
                    int((y - top) * tileSize)
                )
                image.paste(img, box)


class MapBuilder:
    """Строит схему расположения точек"""
    
    def __init__(self):
        self.converter = CoordinateConverter()
    
    def create_map(self, project: ProjectData, use_osm: bool = False,
                   output_path: Optional[str] = None, width: float = 16, height: float = 10) -> str:
        """
        Создает PNG изображение схемы (полная версия как в оригинале)
        """
        # Собираем данные для отображения
        map_data = self._collect_map_data(project)
        
        if not map_data['has_data']:
            return None
        
        # Создаем фигуру с заданными размерами для лучшего качества при масштабировании
        fig, ax = plt.subplots(figsize=(width, height))  # Размеры задаются параметрами
        
        # Конвертируем все координаты в WGS84 для отображения
        wgs84_data = self._convert_to_wgs84(map_data)
        
        # Определяем границы области
        all_lons = (wgs84_data['traj_lon'] + wgs84_data['gcp_lon'] + 
                   wgs84_data['check_lon'])
        all_lats = (wgs84_data['traj_lat'] + wgs84_data['gcp_lat'] + 
                   wgs84_data['check_lat'])
        
        if not all_lons or not all_lats:
            plt.close(fig)
            return None
        
        lon_min, lon_max = min(all_lons), max(all_lons)
        lat_min, lat_max = min(all_lats), max(all_lats)
        
        # Добавляем отступ 20%
        lon_pad = (lon_max - lon_min) * 0.20
        lat_pad = (lat_max - lat_min) * 0.20
        lon_min_display = lon_min - lon_pad
        lon_max_display = lon_max + lon_pad
        lat_min_display = lat_min - lat_pad
        lat_max_display = lat_max + lat_pad
        
        # Преобразуем в UTM для корректного масштаба
        utm_data = self._convert_to_utm(wgs84_data, lon_min_display, lon_max_display,
                                        lat_min_display, lat_max_display)
        
        # Добавляем подложку OSM если нужно
        if use_osm:
            self._add_osm_background(ax, wgs84_data, utm_data, lon_min_display,
                                     lon_max_display, lat_min_display, lat_max_display)
        else:
            # Устанавливаем границы в UTM координатах и используем белый фон
            ax.set_xlim(utm_data['x_min'], utm_data['x_max'])
            ax.set_ylim(utm_data['y_min'], utm_data['y_max'])
            ax.set_facecolor('white')
            # Убедимся, что оси имеют равные пропорции для правильного отображения
            ax.set_aspect('equal', adjustable='box')
        
        # Рисуем траекторию/станции
        self._draw_trajectory(ax, utm_data, project)
        
        # Рисуем опорные точки
        self._draw_points(ax, utm_data['gcp_x'], utm_data['gcp_y'], 
                         utm_data['gcp_names'], 'gcp')
        
        # Рисуем контрольные точки
        self._draw_points(ax, utm_data['check_x'], utm_data['check_y'], 
                         utm_data['check_names'], 'checkpoint')
        
        # Настройки графика
        ax.legend(loc='upper left', bbox_to_anchor=(0, -0.01),
                 ncol=3, framealpha=0.95)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.set_xticks([])
        ax.set_yticks([])
        
        ax.margins(0.1)
        # Убедимся, что ось равносторонняя для корректного масштаба
        ax.set_aspect('equal', adjustable='box')
        plt.tight_layout(pad=2.0)
        
        # Сохраняем
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            output_path = temp_file.name
            temp_file.close()
        
        plt.savefig(output_path, dpi=150, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close(fig)
        
        project.map_image_path = output_path
        project.used_osm_map = use_osm  # Устанавливаем флаг использования OSM подложки
        return output_path
    
    def _collect_map_data(self, project: ProjectData) -> dict:
        """Собирает данные для отображения на карте"""
        result = {
            'traj_x': [], 'traj_y': [], 'traj_z': [],
            'traj_segments': [],  # Информация о сегментах траектории
            'gcp_x': [], 'gcp_y': [], 'gcp_z': [], 'gcp_names': [],
            'check_x': [], 'check_y': [], 'check_z': [], 'check_names': [],
            'has_data': False
        }
        
        # Траектория/станции
        if len(project.trajectory.x) > 0:
            result['traj_x'] = project.trajectory.x.tolist()
            result['traj_y'] = project.trajectory.y.tolist()
            result['traj_z'] = project.trajectory.z.tolist()
            # Сохраняем информацию о сегментах траектории
            result['traj_segments'] = project.trajectory.trajectory_segments
        
        # Опорные точки (используем x_map, y_map, z_map)
        for point in project.get_gcps():
            if point.x_map is not None:
                result['gcp_x'].append(point.x_map)
                result['gcp_y'].append(point.y_map)
                result['gcp_z'].append(point.z_map)
                result['gcp_names'].append(point.name)
        
        # Контрольные точки
        for point in project.get_checkpoints():
            if point.x_map is not None:
                result['check_x'].append(point.x_map)
                result['check_y'].append(point.y_map)
                result['check_z'].append(point.z_map)
                result['check_names'].append(point.name)
        
        result['has_data'] = (len(result['traj_x']) > 0 or
                             len(result['gcp_x']) > 0 or
                             len(result['check_x']) > 0)
        
        return result
    
    def _convert_to_wgs84(self, map_data: dict) -> dict:
        """Конвертирует ECEF координаты в WGS84"""
        result = {
            'traj_lat': [], 'traj_lon': [],
            'traj_segments': [],  # Информация о сегментах траектории
            'gcp_lat': [], 'gcp_lon': [], 'gcp_names': [],
            'check_lat': [], 'check_lon': [], 'check_names': []
        }
        
        # Траектория
        for x, y, z in zip(map_data['traj_x'], map_data['traj_y'], map_data['traj_z']):
            lat, lon, _ = self.converter.ecef_to_wgs84(x, y, z)
            result['traj_lat'].append(lat)
            result['traj_lon'].append(lon)
        
        # Передаем информацию о сегментах траектории
        if 'traj_segments' in map_data:
            result['traj_segments'] = map_data['traj_segments']
        
        # Опорные точки
        for x, y, z in zip(map_data['gcp_x'], map_data['gcp_y'], map_data['gcp_z']):
            lat, lon, _ = self.converter.ecef_to_wgs84(x, y, z)
            result['gcp_lat'].append(lat)
            result['gcp_lon'].append(lon)
        
        # Передаем имена опорных точек
        result['gcp_names'] = map_data.get('gcp_names', [])
        
        # Контрольные точки
        for x, y, z in zip(map_data['check_x'], map_data['check_y'], map_data['check_z']):
            lat, lon, _ = self.converter.ecef_to_wgs84(x, y, z)
            result['check_lat'].append(lat)
            result['check_lon'].append(lon)
        
        # Передаем имена контрольных точек
        result['check_names'] = map_data.get('check_names', [])
        
        return result
    
    def _convert_to_utm(self, wgs84_data: dict, lon_min, lon_max, lat_min, lat_max) -> dict:
        """Конвертирует WGS84 координаты в UTM"""
        center_lon = (lon_min + lon_max) / 2
        center_lat = (lat_min + lat_max) / 2
        
        # Определяем UTM зону
        utm_zone = int((center_lon + 180) / 6) + 1
        epsg_code = f"EPSG:326{utm_zone:02d}" if center_lat >= 0 else f"EPSG:327{utm_zone:02d}"
        
        transformer = pyproj.Transformer.from_crs("EPSG:4326", epsg_code, always_xy=True)
        
        result = {
            'traj_x': [], 'traj_y': [],
            'traj_segments': [],  # Информация о сегментах траектории
            'gcp_x': [], 'gcp_y': [], 'gcp_names': [],
            'check_x': [], 'check_y': [], 'check_names': [],
            'x_min': None, 'x_max': None, 'y_min': None, 'y_max': None
        }
        
        # Конвертируем траекторию
        if wgs84_data['traj_lon']:
            x, y = transformer.transform(wgs84_data['traj_lon'], wgs84_data['traj_lat'])
            result['traj_x'] = x.tolist() if hasattr(x, 'tolist') else list(x)
            result['traj_y'] = y.tolist() if hasattr(y, 'tolist') else list(y)
            # Передаем информацию о сегментах траектории
            if 'traj_segments' in wgs84_data:
                result['traj_segments'] = wgs84_data['traj_segments']
        
        # Конвертируем опорные точки
        if wgs84_data['gcp_lon']:
            x, y = transformer.transform(wgs84_data['gcp_lon'], wgs84_data['gcp_lat'])
            result['gcp_x'] = x.tolist() if hasattr(x, 'tolist') else list(x)
            result['gcp_y'] = y.tolist() if hasattr(y, 'tolist') else list(y)
            result['gcp_names'] = wgs84_data.get('gcp_names', [])
        
        # Конвертируем контрольные точки
        if wgs84_data['check_lon']:
            x, y = transformer.transform(wgs84_data['check_lon'], wgs84_data['check_lat'])
            result['check_x'] = x.tolist() if hasattr(x, 'tolist') else list(x)
            result['check_y'] = y.tolist() if hasattr(y, 'tolist') else list(y)
            result['check_names'] = wgs84_data.get('check_names', [])
        
        # Конвертируем угловые точки
        corners_x, corners_y = transformer.transform(
            [lon_min, lon_max], [lat_min, lat_max]
        )
        result['x_min'], result['x_max'] = min(corners_x), max(corners_x)
        result['y_min'], result['y_max'] = min(corners_y), max(corners_y)
        
        return result
    
    def _add_osm_background(self, ax, wgs84_data, utm_data, lon_min, lon_max, lat_min, lat_max):
        """Добавляет подложку OSM"""
        try:
            imgWidth, imgHeight = 1200, 900
            padLeft, padTop = 80, 80
            
            center_lat = (lat_min + lat_max) / 2
            center_lon = (lon_min + lon_max) / 2
            
            # Расчет zoom уровня
            zoom = 18
            x_range = 2 * 180.0
            y_range = 2 * math.degrees(math.atan(math.sinh(math.pi)))
            y_range = y_range / math.cos(math.radians(center_lat))
            
            while zoom > 0:
                n = 2.0 ** zoom
                lon_pixels = tileSize * n / x_range * (lon_max - lon_min)
                lat_pixels = tileSize * n / y_range * (lat_max - lat_min)
                if (lon_pixels + padLeft < imgWidth) and (lat_pixels + padTop < imgHeight):
                    break
                zoom -= 1
            
            zoom = max(1, min(zoom, 18))
            
            static_map = StaticMap(
                imgSize=(imgWidth, imgHeight),
                imgPadding=(padLeft, padTop)
            )
            
            # Добавляем все точки
            all_lats = (wgs84_data['traj_lat'] + wgs84_data['gcp_lat'] +
                       wgs84_data['check_lat'])
            all_lons = (wgs84_data['traj_lon'] + wgs84_data['gcp_lon'] +
                       wgs84_data['check_lon'])
            
            for lat, lon in zip(all_lats, all_lons):
                static_map.addMarker(lat, lon)
            
            map_image = static_map.createMap(maxZoom=zoom)
            background_image = np.array(map_image)
            
            # Расчет экстента карты
            center_xtile, center_ytile = deg2tile(center_lat, center_lon, zoom)
            
            top = center_ytile - (imgHeight * 0.5) / tileSize
            bottom = center_ytile + (imgHeight * 0.5) / tileSize
            left = center_xtile - (imgWidth * 0.5) / tileSize
            right = center_xtile + (imgWidth * 0.5) / tileSize
            
            top_left_lat, top_left_lon = tile2deg(left, top, zoom)
            bottom_right_lat, bottom_right_lon = tile2deg(right, bottom, zoom)
            
            # Преобразуем углы в UTM
            transformer = pyproj.Transformer.from_crs("EPSG:4326",
                f"EPSG:326{int((center_lon+180)/6)+1:02d}" if center_lat >= 0
                else f"EPSG:327{int((center_lon+180)/6)+1:02d}",
                always_xy=True)
            
            top_left_x, top_left_y = transformer.transform(top_left_lon, top_left_lat)
            bottom_right_x, bottom_right_y = transformer.transform(bottom_right_lon, bottom_right_lat)
            
            ax.imshow(
                background_image,
                extent=(top_left_x, bottom_right_x, bottom_right_y, top_left_y),
                aspect='equal',
                origin='upper',
                alpha=0.7
            )
            
            ax.set_xlim(utm_data['x_min'], utm_data['x_max'])
            ax.set_ylim(utm_data['y_min'], utm_data['y_max'])
            
        except Exception as e:
            print(f"Ошибка создания OSM подложки: {e}")
            # При ошибке установки OSM подложки, устанавливаем белый фон и корректные границы
            ax.set_xlim(utm_data['x_min'], utm_data['x_max'])
            ax.set_ylim(utm_data['y_min'], utm_data['y_max'])
            ax.set_facecolor('white')
            # Убедимся, что оси имеют равные пропорции для правильного отображения
            ax.set_aspect('equal', adjustable='box')
    
    def _draw_trajectory(self, ax, utm_data, project):
        """Рисует траекторию или станции"""
        if len(utm_data['traj_x']) > 0:
            if project.project_type == "rs10":
                # Для RS10 рисуем линию траектории, учитывая сегменты
                # Если у проекта есть информация о сегментах траектории
                if 'traj_segments' in utm_data and utm_data['traj_segments']:
                    # Рисуем каждый сегмент отдельно, чтобы не соединять разные траектории
                    for idx, (start_idx, end_idx) in enumerate(utm_data['traj_segments']):
                        if start_idx < len(utm_data['traj_x']) and end_idx <= len(utm_data['traj_x']):
                            seg_x = utm_data['traj_x'][start_idx:end_idx]
                            seg_y = utm_data['traj_y'][start_idx:end_idx]
                            
                            # Рисуем линию для сегмента
                            ax.plot(seg_x, seg_y,
                                   color=MAP_COLORS['trajectory'], linewidth=2.5, alpha=0.9,
                                   label='Траектория' if idx == 0 else "",
                                   zorder=5)
                else:
                    # Если нет информации о сегментах, рисуем как раньше
                    ax.plot(utm_data['traj_x'], utm_data['traj_y'],
                           color=MAP_COLORS['trajectory'], linewidth=2.5, alpha=0.9,
                           label='Траектория', zorder=5)
                
                # Точки траектории
                ax.scatter(utm_data['traj_x'], utm_data['traj_y'],
                          c=MAP_COLORS['trajectory_point'], s=15, marker='o',
                          alpha=0.7, edgecolors='none', zorder=5)
            else:
                # Для MSA рисуем станции
                ax.scatter(utm_data['traj_x'], utm_data['traj_y'],
                          c=MAP_COLORS['station'], s=30, marker='o',
                          label='Станции сканирования', alpha=0.7,
                          edgecolors='black', zorder=5)
    
    def _draw_points(self, ax, x_coords, y_coords, names, point_type):
        """Рисует точки (опорные или контрольные)"""
        if not x_coords:
            return
        
        color = MAP_COLORS['gcp'] if point_type == 'gcp' else MAP_COLORS['checkpoint']
        label = 'Опорные точки' if point_type == 'gcp' else 'Контрольные точки'
        
        ax.scatter(x_coords, y_coords,
                  c=color, s=120, marker='^',
                  label=label, alpha=0.8,
                  edgecolors='black', zorder=6)
        
        # Генерируем имена, если они отсутствуют или пустые
        display_names = []
        for i, name in enumerate(names):
            if name and name.strip():
                display_names.append(name)
            else:
                prefix = 'G' if point_type == 'gcp' else 'C'
                display_names.append(f'{prefix}{i+1}')
        
        for x, y, name in zip(x_coords, y_coords, display_names):
            ax.annotate(name, (x, y),
                       xytext=(0, 15), textcoords='offset points',
                       fontsize=10, fontweight='bold', ha='center', va='bottom', zorder=12,
                       clip_on=True)