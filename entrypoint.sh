#!/bin/bash

# Блок применения миграций базы данных.
# Команда создает или обновляет таблицы перед запуском веб-приложения.
echo "Применяем миграции..."
python manage.py migrate --noinput

# Блок сборки статических файлов.
# collectstatic переносит CSS, JS и изображения в STATIC_ROOT для отдачи сервером.
echo "Собираем статику..."
python manage.py collectstatic --noinput

# Блок запуска Django-сервера.
# 0.0.0.0 делает приложение доступным другим контейнерам в Docker-сети.
echo "Запускаем сервер..."
exec python manage.py runserver 0.0.0.0:8000
