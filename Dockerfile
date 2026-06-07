# Блок выбора базового образа контейнера.
# Slim-образ Python уменьшает размер контейнера и оставляет только необходимую среду выполнения.
FROM python:3.11-slim

# Блок настройки поведения Python внутри контейнера.
# PYTHONDONTWRITEBYTECODE запрещает создание .pyc-файлов, а PYTHONUNBUFFERED сразу выводит логи.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Блок рабочей директории приложения.
# Все дальнейшие команды выполняются внутри /app.
WORKDIR /app

# Блок установки зависимостей.
# Сначала копируется только requirements.txt, чтобы Docker мог кешировать установку библиотек.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Блок копирования исходного кода.
# В контейнер попадают Django-проект, приложение, шаблоны и конфигурационные файлы.
COPY . /app/

# Блок подготовки стартового скрипта.
# entrypoint.sh выполняет миграции, сбор статических файлов и запуск сервера.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Блок публикации порта приложения.
# Django внутри контейнера слушает порт 8000.
EXPOSE 8000

# Блок запуска контейнера.
# ENTRYPOINT передает управление стартовому скрипту.
ENTRYPOINT ["/entrypoint.sh"]
