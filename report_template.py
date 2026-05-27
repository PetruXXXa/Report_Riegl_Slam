"""
Модуль с жестким макетом HTML отчета (шаблон).
"""

class ReportTemplate:
    """Содержит HTML шаблон отчета"""
    
    @staticmethod
    def get_template() -> str:
        """Возвращает HTML шаблон отчета"""
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Отчет уравнивания НЛС</title>
    <style>
        @media print {{
            @page {{
                margin-top: 20mm !important;
                margin-bottom: 20mm !important;
                margin-left: 20mm !important;
                margin-right: 15mm !important;
                size: A4;
            }}
            body {{ 
                margin: 0 !important; 
                padding: 0 !important; 
                font-family: Arial, sans-serif; 
                background-color: white; 
                width: 100%;
            }}
            .report-container {{ 
                max-width: 100%; 
                margin: 0 !important; 
                padding: 0 !important; 
                width: 100%; 
                box-shadow: none !important;
                border-radius: 0 !important;
            }}
            .section {{ margin: 5px 0 !important; padding: 0 !important; }}
            .section.page-break-before {{ page-break-before: always; }}
            .section.no-page-break {{ 
                page-break-before: avoid !important;
            }}
            .subsection {{ margin: 8px 0 !important; padding: 0 !important; }}
            .text-stats {{ margin: 5px 0 !important; padding: 5px !important; }}
            .text-stat-item {{ margin: 2px 0 !important; padding: 2px 0 !important; }}
            h1 {{ margin-top: 0 !important; padding-bottom: 5px !important; }}
            h2 {{ margin-top: 15px !important; margin-bottom: 8px !important; }}
            h3 {{ margin-top: 12px !important; margin-bottom: 6px !important; }}
            h4 {{ margin-top: 10px !important; margin-bottom: 5px !important; }}
            .image-container {{ 
                page-break-inside: avoid !important;
                page-break-before: avoid !important;
                page-break-after: avoid !important;
            }}
            .image-container img {{ 
                width: 100% !important; 
                height: auto !important; 
                max-width: 100% !important;
                object-fit: contain !important;
                display: block !important;
                margin-left: auto !important;
                margin-right: auto !important;
            }}
            .map-container img {{
                width: 100% !important;
                height: auto !important;
                max-width: 100% !important;
                display: block !important;
                margin-left: auto !important;
                margin-right: auto !important;
            }}
            /* Гарантируем, что раздел 2 (схема) помещается на первой странице */
            .section.no-page-break:nth-of-type(2) {{
                max-height: 230mm !important; /* Высота A4 минус поля */
                overflow: hidden !important;
            }}
            h1, h2, h3, h4 {{
                color: black !important;
            }}
            .accuracy-table th, .accuracy-table td {{
                border: 1px solid black !important;
            }}
        }}
        
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            background-color: #f5f5f5; 
            color: #333; 
        }}
        .report-container {{ 
            max-width: 210mm; 
            margin: 20px auto; 
            background-color: white; 
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            border-radius: 5px;
        }}
        h1 {{ 
            color: #2c3e50; 
            border-bottom: 3px solid #3498db; 
            padding-bottom: 10px; 
            text-align: center; 
            margin-top: 0;
        }}
        h2 {{ 
            color: #34495e; 
            border-bottom: 2px solid #bdc3c7; 
            padding-bottom: 5px; 
            margin-top: 30px; 
        }}
        h3 {{ 
            color: #7f8c8d; 
            margin-top: 25px; 
            padding-left: 10px; 
        }}
        h4 {{ 
            color: #2c3e50; 
            margin-top: 20px; 
            margin-bottom: 10px;
        }}
        .section {{ 
            margin: 20px 0; 
            padding: 20px; 
            background-color: #f9f9f9; 
            border-radius: 5px; 
        }}
        .subsection {{ 
            margin: 15px 0; 
            padding: 15px; 
            background-color: white; 
            border-radius: 5px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .image-container {{ 
            margin: 15px 0; 
            text-align: center; 
        }}
        .image-container img {{
            width: 100%;
            height: auto;
            max-width: 100%;
        }}
        
        .map-container {{
            position: relative;
            width: 100%;
        }}
        
        .map-container img {{
            width: 100%;
            height: auto;
            max-width: 100%;
            object-fit: contain;
        }}
        
        .map-caption {{
            font-size: 0.8em;
            text-align: right;
            color: #666;
            margin-top: 5px;
            padding: 2px 5px;
            border-top: 1px solid #eee;
        }}
        .caption {{ 
            margin-top: 10px; 
            font-style: italic; 
            color: #7f8c8d; 
            font-size: 0.9em; 
        }}
        .project-info {{ 
            background-color: #ecf0f1; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 10px 0; 
        }}
        .stats {{ 
            display: flex; 
            flex-wrap: wrap; 
            gap: 20px; 
            margin: 20px 0; 
        }}
        .stat-card {{ 
            background: linear-gradient(135deg, #3498db, #2980b9); 
            color: white; 
            padding: 15px 25px; 
            border-radius: 5px; 
            flex: 1; 
            min-width: 150px; 
            text-align: center; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .stat-card span {{ 
            font-size: 2em; 
            font-weight: bold; 
            display: block; 
        }}
        .text-stats {{ 
            margin: 20px 0; 
            padding: 15px; 
            background-color: #f8f9fa; 
            border-radius: 5px;
        }}
        .text-stat-item {{ 
            margin: 10px 0; 
            padding: 8px 0; 
            border-bottom: 1px solid #e9ecef; 
            display: flex;
            align-items: center;
        }}
        .text-stat-item:last-child {{ 
            border-bottom: none; 
        }}
        .text-stat-label {{ 
            font-weight: bold; 
            color: #2c3e50; 
            display: inline-block; 
            width: 250px; 
        }}
        .text-stat-value {{ 
            font-weight: bold; 
            color: #2980b9; 
            font-size: 1.1em; 
            margin-left: 20px;
        }}
        .footer {{ 
            margin-top: 30px; 
            text-align: center; 
            color: #7f8c8d; 
            font-size: 0.9em; 
            border-top: 1px solid #bdc3c7; 
            padding-top: 20px; 
        }}
        .table-container {{ 
            margin: 15px 0; 
            width: 100%; 
            overflow-x: auto;
        }}
        .accuracy-table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin: 10px 0; 
            font-size: 0.9em; 
            background-color: white;
            border: 1px solid black;
        }}
        .accuracy-table th {{ 
            background-color: #3498db; 
            color: white; 
            padding: 3px 6px; 
            border: 1px solid black; 
            font-weight: bold;
            text-align: center;
            font-size: 1em;
        }}
        .accuracy-table td {{ 
            padding: 1px 6px; 
            border: 1px solid black; 
            text-align: center; 
            font-size: 0.95em;
        }}
        .accuracy-table tr:nth-child(even) {{ 
            background-color: #f8f9fa; 
        }}
        .accuracy-table tr:hover {{
            background-color: #e8f4f8;
        }}
        @media print {{
            .accuracy-table {{
                border: 1pt solid black !important;
                box-shadow: none !important;
                border-collapse: collapse !important;
            }}
            .accuracy-table th {{
                background-color: #d9d9d9 !important;
                color: black !important;
                border: 1pt solid black !important;
                padding: 3px 6px !important;
                font-weight: bold;
            }}
            .accuracy-table td {{
                border: 1pt solid black !important;
                padding: 1px 6px !important;
            }}
            .accuracy-table tr:nth-child(even) {{
                background-color: #f2f2f2 !important;
            }}
        }}
        .note {{ 
            background-color: #fcf8e3; 
            padding: 10px 15px; 
            margin: 10px 0; 
            border-left: 4px solid #f39c12;
            border-radius: 3px;
        }}
        .warning {{
            background-color: #f8d7da;
            color: #721c24;
            padding: 10px 15px;
            margin: 10px 0;
            border-left: 4px solid #dc3545;
            border-radius: 3px;
        }}
        .success {{
            background-color: #d4edda;
            color: #155724;
            padding: 10px 15px;
            margin: 10px 0;
            border-left: 4px solid #28a745;
            border-radius: 3px;
        }}
        @media (max-width: 768px) {{
            .report-container {{ padding: 10px; margin: 10px; }}
            .text-stat-label {{ width: 180px; }}
            .accuracy-table {{ font-size: 0.8em; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <h1>Отчет уравнивания НЛС</h1>
        
        <!-- Раздел 1: Общая статистика -->
        <div class="section no-page-break">
            <h2>1. Общая статистика</h2>
            <div class="text-stats">
                {total_stats}
            </div>
        </div>
        
        <!-- Раздел 2: Схема опорных и контрольных точек -->
        <div class="section no-page-break">
            <h2>2. Схема опорных и контрольных точек</h2>
            <div class="image-container">
                {map_image}
            </div>
        </div>
        
        <!-- Раздел 3: Таблицы опорных и контрольных точек -->
        <div class="section page-break-before">
            <h2>3. Таблицы опорных и контрольных точек</h2>
            <div class="table-container">
                {points_tables}
            </div>
        </div>
        
        <!-- Раздел 4: Анализ точности -->
        <div class="section page-break-before">
            <h2>4. Анализ точности</h2>
            
            <!-- 4.1 Опорные точки -->
            <div class="subsection">
                <h3>4.1 Анализ опорных точек</h3>
                
                <!-- 4.1.1 Отклонения опорных точек -->
                <h4>4.1.1 Отклонения опорных точек</h4>
                <div class="table-container">
                    {control_deviations_table}
                </div>
                
                <!-- 4.1.2 Статистика опорных точек -->
                <h4>4.1.2 Статистика опорных точек</h4>
                <div class="table-container">
                    {control_stats_table}
                </div>
                
                <!-- 4.1.3 График отклонений опорных точек -->
                <h4>4.1.3 График оценки точности опорных точек</h4>
                <div class="image-container">
                    {control_graph}
                </div>
            </div>
            
            <!-- 4.2 Контрольные точки -->
            <div class="subsection">
                <h3>4.2 Анализ контрольных точек</h3>
                
                <!-- 4.2.1 Отклонения контрольных точек -->
                <h4>4.2.1 Отклонения контрольных точек</h4>
                <div class="table-container">
                    {check_deviations_table}
                </div>
                
                <!-- 4.2.2 Статистика контрольных точек -->
                <h4>4.2.2 Статистика контрольных точек</h4>
                <div class="table-container">
                    {check_stats_table}
                </div>
                
                <!-- 4.2.3 График отклонений контрольных точек -->
                <h4>4.2.3 График оценки точности контрольных точек</h4>
                <div class="image-container">
                    {check_graph}
                </div>
            </div>
        </div>
        
        
    </div>
</body>
</html>
        """