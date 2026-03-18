"""
Модуль для экспорта отчета в PDF и Word (шаг 9).
"""

import os
import tempfile
import subprocess
import re
import base64
import mimetypes
from typing import Optional, List, Tuple
import uuid


class ReportExporter:
    """Экспортирует отчет в различные форматы"""
    
    def export_to_pdf(self, html_content: str, output_path: str) -> bool:
        """
        Экспортирует HTML в PDF
        Требует установки wkhtmltopdf
        """
        try:
            # Сохраняем HTML во временный файл
            temp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
            temp_html_path = temp_html.name
            temp_html.write(html_content)
            temp_html.close()
            
            # Конвертируем в PDF
            cmd = ['wkhtmltopdf', temp_html_path, output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Удаляем временный файл
            os.unlink(temp_html_path)
            
            return result.returncode == 0
            
        except FileNotFoundError:
            print("Ошибка: wkhtmltopdf не найден. Убедитесь, что он установлен и добавлен в PATH.")
            return False
        except Exception as e:
            print(f"Ошибка экспорта в PDF: {e}")
            return False
    
    def export_to_word(self, html_content: str, output_path: str) -> bool:
        """
        Экспортирует HTML в Word
        Просто сохраняет HTML как .doc (Word может открыть)
        """
        try:
            # Создаем DOC-совместимый HTML
            doc_html = self._create_doc_compatible_html(html_content)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(doc_html)
            return True
        except Exception as e:
            print(f"Ошибка экспорта в Word: {e}")
            return False
    
    def _create_doc_compatible_html(self, html_content: str) -> str:
        """
        Создает DOC-совместимый HTML с inline стилями.
        Word плохо интерпретирует внешние CSS, поэтому используем inline стили.
        """
        # Извлекаем содержимое body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_content = body_match.group(1)
        else:
            body_content = html_content
        
        # Удаляем лишние теги style и script
        body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Создаем простой HTML с inline стилями
        doc_html = f"""<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:w="urn:schemas-microsoft-com:office:word"
      xmlns="http://www.w3.org/TR/REC-html40">
<head>
    <meta charset="UTF-8">
    <meta name="ProgId" content="Word.Document">
    <meta name="Generator" content="Microsoft Word 15">
    <meta name="Originator" content="Microsoft Word 15">
    <title>Отчет уравнивания НЛС</title>
    <!--[if gte mso 9]>
    <xml>
        <w:WordDocument>
            <w:View>Print</w:View>
            <w:Zoom>100</w:Zoom>
            <w:DoNotOptimizeForBrowser/>
        </w:WordDocument>
    </xml>
    <![endif]-->
    <style>
        /* Минимальные стили для Word */
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0 !important; 
            padding: 0 !important; 
            font-size: 11pt; 
        }}
        @page {{
            margin-top: 20mm !important;
            margin-bottom: 20mm !important;
            margin-left: 20mm !important;
            margin-right: 15mm !important;
            size: A4;
        }}
        @page WordSection1 {{
            size: 21.0cm 29.7cm;
            margin: 2.0cm 1.5cm 2.0cm 2.0cm;
            mso-header-margin: 1.0cm;
            mso-footer-margin: 1.0cm;
            mso-paper-source: 0;
        }}
        div.WordSection1 {{
            page: WordSection1;
        }}
        h1 {{ 
            color: #000000; 
            text-align: center; 
            font-size: 16pt; 
            margin-top: 0; 
            margin-bottom: 20pt; 
        }}
        h2 {{ 
            color: #000000; 
            font-size: 14pt; 
            margin-top: 20pt; 
            margin-bottom: 10pt; 
            border-bottom: 1pt solid #000000; 
            padding-bottom: 3pt; 
        }}
        h3 {{ 
            color: #000000; 
            font-size: 12pt; 
            margin-top: 15pt; 
            margin-bottom: 8pt; 
        }}
        h4 {{ 
            color: #000000; 
            font-size: 11pt; 
            margin-top: 12pt; 
            margin-bottom: 6pt; 
            font-weight: bold; 
        }}
        .section {{ 
            margin: 10pt 0; 
        }}
        .no-page-break {{ 
            /* Для Word используем разрыв страницы через CSS */
            page-break-inside: avoid; 
        }}
        .page-break-before {{ 
            page-break-before: always; 
        }}
        .image-container img {{ 
            width: 100%; 
            max-width: 175mm;  /* Ширина A4 минус поля (20мм слева + 15мм справа) */
            height: auto; 
            display: block;
            margin-left: auto;
            margin-right: auto;
        }}
        .accuracy-table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin: 10pt 0; 
            font-size: 10pt; 
            border: 1pt solid #000000; 
        }}
        .accuracy-table th {{ 
            background-color: #D9D9D9; 
            color: #000000; 
            padding: 5pt; 
            border: 1pt solid #000000; 
            font-weight: bold; 
            text-align: center; 
        }}
        .accuracy-table td {{ 
            padding: 4pt; 
            border: 1pt solid #000000; 
            text-align: center; 
        }}
        .text-stat-item {{ 
            margin: 5pt 0; 
        }}
        .text-stat-label {{ 
            font-weight: bold; 
            display: inline-block; 
            width: 200pt; 
        }}
        .text-stat-value {{ 
            font-weight: bold; 
        }}
        .footer {{ 
            margin-top: 20pt; 
            text-align: center; 
            font-size: 9pt; 
            color: #666666; 
            border-top: 0.5pt solid #CCCCCC; 
            padding-top: 10pt; 
        }}
    </style>
</head>
<body>
<div class="WordSection1">
{body_content}
</div>
</body>
</html>"""
        
        return doc_html
    
    def export_to_word_enhanced(self, html_content: str, output_path: str) -> bool:
        """
        Экспортирует HTML в Word с сохранением форматирования и изображений
        Использует MHTML формат, который Word может открывать
        """
        try:
            # Определяем расширение файла
            ext = os.path.splitext(output_path)[1].lower()
            
            if ext == '.docx':
                # Для DOCX используем pandoc если доступен
                if self._is_pandoc_available():
                    return self.export_with_pandoc(html_content, output_path, 'docx')
                else:
                    print("Pandoc не найден. Для DOCX экспорта установите pandoc.")
                    print("Сохраняем как MHTML с расширением .docx")
                    # Fallback к MHTML с изменением расширения
                    return self._export_to_mhtml(html_content, output_path)
            
            elif ext == '.doc':
                # Для DOC используем улучшенный HTML экспорт (не DOCX!)
                # Word может открывать HTML файлы с расширением .doc
                return self.export_to_word(html_content, output_path)
            
            elif ext in ['.mht', '.mhtml']:
                return self._export_to_mhtml(html_content, output_path)
            
            else:
                # По умолчанию используем MHTML
                return self._export_to_mhtml(html_content, output_path + '.mht')
                
        except Exception as e:
            print(f"Ошибка улучшенного экспорта в Word: {e}")
            # Fallback к простому методу
            return self.export_to_word(html_content, output_path)
    
    def _is_pandoc_available(self) -> bool:
        """Проверяет, доступен ли pandoc в системе"""
        try:
            result = subprocess.run(['pandoc', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except (FileNotFoundError, OSError):
            return False
    
    def _export_to_mhtml(self, html_content: str, output_path: str) -> bool:
        """
        Экспортирует HTML в MHTML формат (MIME HTML)
        Word может открывать такие файлы с сохранением изображений
        """
        try:
            # Извлекаем изображения из HTML и заменяем data URI на ссылки
            html_modified = html_content
            images = []
            
            # Ищем все теги img с data URI
            import re
            pattern = r'<img[^>]+src="data:image/([^;]+);base64,([^"]+)"'
            
            def replace_match(match):
                img_type = match.group(1)
                b64_data = match.group(2)
                
                # Определяем content-type
                if img_type == 'png':
                    content_type = 'image/png'
                elif img_type == 'jpeg' or img_type == 'jpg':
                    content_type = 'image/jpeg'
                elif img_type == 'gif':
                    content_type = 'image/gif'
                elif img_type == 'svg+xml':
                    content_type = 'image/svg+xml'
                else:
                    content_type = f'image/{img_type}'
                
                # Генерируем Content-ID
                cid = f"image{len(images)+1}@report"
                images.append((content_type, b64_data, cid))
                
                # Заменяем src на ссылку на MIME часть
                return f'<img src="{cid}" alt="image"'
            
            # Заменяем все data URI
            html_modified = re.sub(pattern, replace_match, html_modified, flags=re.IGNORECASE)
            
            # Генерируем уникальную границу
            boundary = f"----=_NextPart_{uuid.uuid4().hex[:16]}"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # Заголовки MHTML
                f.write("From: <Saved by Report Generator>\n")
                f.write("Subject: Report\n")
                f.write("MIME-Version: 1.0\n")
                f.write(f"Content-Type: multipart/related; type=\"text/html\"; boundary=\"{boundary}\"\n")
                f.write("\n")
                
                # Часть с HTML
                f.write(f"--{boundary}\n")
                f.write("Content-Type: text/html; charset=utf-8\n")
                f.write("Content-Transfer-Encoding: 8bit\n")
                f.write("Content-Location: file:///report.html\n")
                f.write("\n")
                f.write(html_modified)
                f.write("\n")
                
                # Части с изображениями
                for i, (content_type, data_b64, cid) in enumerate(images):
                    f.write(f"--{boundary}\n")
                    f.write(f"Content-Type: {content_type}\n")
                    f.write("Content-Transfer-Encoding: base64\n")
                    f.write(f"Content-Location: {cid}\n")
                    f.write("\n")
                    # Записываем base64 с разбивкой по строкам
                    for j in range(0, len(data_b64), 76):
                        f.write(data_b64[j:j+76] + "\n")
                    f.write("\n")
                
                # Закрывающая граница
                f.write(f"--{boundary}--\n")
            
            return True
        except Exception as e:
            print(f"Ошибка экспорта в MHTML: {e}")
            return False
    

    
    def export_with_pandoc(self, html_content: str, output_path: str, format: str = 'docx') -> bool:
        """
        Экспорт с использованием pandoc (более качественный)
        Требует установки pandoc
        """
        try:
            temp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
            temp_html_path = temp_html.name
            temp_html.write(html_content)
            temp_html.close()
            
            cmd = ['pandoc', temp_html_path, '-o', output_path]
            if format == 'docx':
                cmd.extend(['--to', 'docx'])
                # Устанавливаем поля страницы (в миллиметрах)
                # Pandoc использует переменные geometry: top, bottom, left, right
                cmd.extend(['-V', 'geometry:top=20mm'])
                cmd.extend(['-V', 'geometry:bottom=20mm'])
                cmd.extend(['-V', 'geometry:left=20mm'])
                cmd.extend(['-V', 'geometry:right=15mm'])
                cmd.extend(['-V', 'geometry:paper=a4'])
            elif format == 'pdf':
                cmd.extend(['--to', 'pdf', '--pdf-engine=wkhtmltopdf'])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(temp_html_path)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Ошибка экспорта с pandoc: {e}")
            return False