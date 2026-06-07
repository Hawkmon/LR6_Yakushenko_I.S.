#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


# Блок запуска административных команд Django.
def main():
    """Run administrative tasks."""
    # Переменная DJANGO_SETTINGS_MODULE указывает, какой файл настроек использовать.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
    try:
        # execute_from_command_line обрабатывает команды migrate, runserver, collectstatic и другие.
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # sys.argv передает Django аргументы командной строки.
    execute_from_command_line(sys.argv)


# Блок прямого запуска файла.
if __name__ == '__main__':
    main()
