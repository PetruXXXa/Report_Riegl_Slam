"""
Основной модуль запуска программы.
"""

import tkinter as tk
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui import MSAReportGUI


class Application:
    """Класс-обертка для управления приложением"""
    
    def __init__(self):
        self.root = None
        self.app = None
    
    def run(self):
        """Запускает приложение"""
        self.root = tk.Tk()
        self.app = MSAReportGUI(self.root)
        
        # Устанавливаем обработчик закрытия
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Запускаем главный цикл
        self.root.mainloop()
    
    def on_closing(self):
        """Обработчик закрытия окна"""
        try:
            # Проверяем, существует ли еще окно
            if self.root and self.root.winfo_exists():
                # Очищаем временные файлы в приложении
                if hasattr(self.app, 'filler'):
                    self.app.filler.cleanup_temp_files()
                
                # Уничтожаем окно
                self.root.quit()  # Сначала выходим из mainloop
                self.root.destroy()  # Затем уничтожаем окно
        except (tk.TclError, RuntimeError, AttributeError):
            # Окно уже уничтожено или другие ошибки - игнорируем
            pass
        finally:
            # Завершаем процесс
            sys.exit(0)


def main():
    """Точка входа в программу"""
    app = Application()
    app.run()


if __name__ == "__main__":
    main()