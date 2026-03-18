"""
Модуль с константами программы.
"""

# Встроенная матрица трансформации MGGT -> WGS84 (зашита в код)
MGGT_TO_WGS84_MATRIX = [
    [-0.606715042, -0.651615980, 0.455866744, 2860624.42],
    [0.794946455, -0.500015797, 0.344024443, 2194910.44],
    [0.00375210805, 0.570471619, 0.822258544, 5243856.29],
    [0.0, 0.0, 0.0, 1.0]
]

# Расстояние для связывания проектов MSA (метры)
PROJECT_CLUSTER_DISTANCE = 20.0

# Цвета для схемы
MAP_COLORS = {
    'trajectory': '#0066CC',
    'trajectory_point': '#3399FF',
    'gcp': 'red',
    'checkpoint': 'green',
    'station': 'blue'
}

# Настройки графиков
GRAPH_SETTINGS = {
    'figure_size': (14, 8),
    'dpi': 150,
    'line_width': 1.5,
    'marker_size': 4
}

# Настройки таблиц
TABLE_SETTINGS = {
    'decimal_places': 4,
    'max_rows_display': 20
}

# Допуски (в метрах)
TOLERANCES = {
    'planar': 0.05,   # 5 см
    'height': 0.08    # 8 см
}