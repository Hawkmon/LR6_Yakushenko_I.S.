# Приложение. Настройка модели реализации качества с помощью Prometheus и Grafana

## 1. Назначение практической части

Для программного средства реализована контейнерная модель мониторинга качества. В качестве системы мониторинга выбран Prometheus, так как он хорошо подходит для контейнерных сред, собирает метрики по pull-модели, поддерживает язык запросов PromQL и легко интегрируется с Grafana для визуального анализа.

Контролируемое программное средство: Django-приложение управления доступом. Приложение запускается в Docker-контейнере `my_auth_app`, публикуется через Nginx `my_nginx`, а метрики собираются Prometheus и отображаются в Grafana.

## 2. Состав контейнерной инфраструктуры

В `docker-compose.yml` добавлены следующие сервисы:

| Контейнер | Назначение |
|---|---|
| `my_auth_app` | Django-приложение, отдающее пользовательский интерфейс и endpoint `/metrics`. |
| `my_nginx` | Reverse proxy для приложения и источник Nginx-статистики через `/stub_status`. |
| `my_postgres` | Контейнер PostgreSQL как элемент инфраструктуры приложения. |
| `my_prometheus` | Сбор и хранение метрик приложения, Nginx, PostgreSQL и Docker-контейнеров. |
| `my_grafana` | Визуализация модели качества на dashboard `Auth App Quality Monitoring`. |
| `my_cadvisor` | Сбор ресурсных метрик Docker-контейнеров: CPU, RAM, I/O. |
| `my_postgres_exporter` | Экспорт технических метрик PostgreSQL в формате Prometheus. |
| `my_nginx_exporter` | Экспорт статистики Nginx в формате Prometheus. |

## 3. Метрики качества

Для приложения реализован endpoint:

```text
http://localhost/metrics
```

Prometheus внутри Docker-сети обращается к приложению по адресу:

```text
http://nginx:80/metrics
```

Основные метрики:

| Метрика | Тип | Связь с ГОСТ Р ИСО/МЭК 25010 |
|---|---|---|
| `auth_app_up` | gauge | Надежность: доступность программного средства. |
| `auth_app_uptime_seconds` | gauge | Надежность: непрерывность работы без перезапуска. |
| `auth_app_request_total` | counter | Производительность и надежность: количество запросов и HTTP-статусы. |
| `auth_app_request_duration_seconds_sum` | counter | Эффективность производительности: среднее время ответа. |
| `auth_app_login_attempts_total` | counter | Защищенность: успешные и неуспешные попытки аутентификации. |
| `auth_app_users_total` | gauge | Функциональная пригодность: число настроенных субъектов доступа. |
| `container_cpu_usage_seconds_total` | counter | Эффективность производительности: загрузка CPU контейнеров. |
| `container_memory_usage_bytes` | gauge | Эффективность производительности: потребление RAM контейнерами. |
| `pg_up` | gauge | Надежность инфраструктуры БД. |
| `nginx_connections_active` | gauge | Производительность сетевого входа приложения. |

## 4. Файлы настройки

Конфигурация Prometheus находится в файле:

```text
prometheus/prometheus.yml
```

В нем описаны job:

| Job | Target | Назначение |
|---|---|---|
| `auth_app` | `auth_app:8000` | Метрики Django-приложения. |
| `nginx` | `nginx_exporter:9113` | Метрики reverse proxy. |
| `postgres` | `postgres_exporter:9187` | Метрики PostgreSQL. |
| `containers` | `cadvisor:8080` | Метрики Docker-контейнеров. |
| `prometheus` | `prometheus:9090` | Самоконтроль Prometheus. |

Grafana настраивается автоматически через provisioning:

```text
grafana/provisioning/datasources/prometheus.yml
grafana/provisioning/dashboards/dashboards.yml
grafana/dashboards/auth-quality-dashboard.json
```

После запуска datasource Prometheus и dashboard создаются без ручной настройки.

## 5. Запуск практического примера

Из корня проекта выполнить:

```bash
docker compose up -d --build
```

Проверить состояние контейнеров:

```bash
docker compose ps
```

Открыть интерфейсы:

| Сервис | Адрес |
|---|---|
| Приложение | `http://localhost/` |
| Prometheus | `http://localhost:9090/` |
| Grafana | `http://localhost:3000/` |
| Adminer | `http://localhost:8080/` |
| cAdvisor | `http://localhost:8081/` |

Учетные данные Grafana:

```text
login: admin
password: admin
```

Dashboard расположен в папке `Quality` и называется `Auth App Quality Monitoring`.

## 6. Проверка сбора метрик

В Prometheus открыть раздел `Status -> Targets`. Все targets должны иметь состояние `UP`:

```text
prometheus
auth_app
nginx
postgres
containers
```

Для ручной проверки выполнить PromQL-запросы:

```promql
auth_app_up
sum(rate(auth_app_request_total[5m]))
sum by (status, reason) (increase(auth_app_login_attempts_total[1h]))
1000 * sum by (route) (rate(auth_app_request_duration_seconds_sum[5m])) / sum by (route) (rate(auth_app_request_total[5m]))
sum by (name) (container_memory_usage_bytes{name=~"my_auth_app|my_nginx|my_postgres|my_prometheus|my_grafana"})
```

## 7. Практическая интерпретация результатов

Модель мониторинга позволяет оценивать качество программного средства по нескольким измеримым признакам:

| Характеристика качества | Измеримый показатель | Критерий оценки |
|---|---|---|
| Надежность | `auth_app_up`, `up`, `auth_app_uptime_seconds` | Приложение и инфраструктурные targets доступны, uptime растет. |
| Производительность | Среднее время ответа, CPU и RAM контейнеров | Время ответа стабильно, контейнер не расходует ресурсы аномально. |
| Защищенность | `auth_app_login_attempts_total` по `status` и `reason` | Видно число отказов входа по неверному пользователю, паролю, IP или времени. |
| Сопровождаемость | Единый dashboard и стандартизированные метрики | Состояние системы понятно без ручного анализа логов. |
| Функциональная пригодность | Метрики маршрутов и аутентификации | Основные функции приложения наблюдаемы и проверяемы. |

## 8. Вывод по практической части

В ходе практической части была развернута контейнерная система мониторинга качества программного средства. Prometheus собирает метрики приложения, Nginx, PostgreSQL и Docker-контейнеров, а Grafana отображает показатели на dashboard. Полученная модель позволяет контролировать доступность, производительность, ресурсное потребление и события аутентификации, что соответствует задаче реализации измеримых свойств качества программного средства по ГОСТ Р ИСО/МЭК 25010.
