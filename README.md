
# Prompt Injection Detection System

## 1. Описание проекта

Проект разработан в рамках лабораторной работы №1 по подготовке защищенного окружения для ML-системы.

**Направление:** Natural Language Processing (NLP).

**Задача:** разработка модели бинарной классификации текстовых запросов для обнаружения prompt injection-атак на большие языковые модели.

Входные данные — текст пользовательского запроса.

Выходные данные:
- 0 — BENIGN (безопасный запрос);
- 1 — INJECTION (потенциальная атака).

Потенциальные пользователи системы — разработчики LLM-приложений, RAG-систем, AI-агентов и корпоративных интеллектуальных помощников.

## 2. Используемый датасет

**Название:** S-Labs/prompt-injection-dataset

**Источник:** https://huggingface.co/datasets/S-Labs/prompt-injection-dataset

**Тип данных:** текстовые запросы.

**Количество признаков:** один текстовый признак `text` и целевая переменная `label`.

**Количество классов:** 2.

**Общее количество объектов:** 15 291.

### Распределение данных

| Выборка | BENIGN | INJECTION | Всего |
|---|---:|---:|---:|
| Train | 6303 | 4786 | 11089 |
| Validation | 1050 | 1051 | 2101 |
| Test | 1050 | 1051 | 2101 |
| Итого | 8403 | 6888 | 15291 |

В обучающей выборке обнаружен умеренный дисбаланс: 56,84% безопасных запросов и 43,16% атак.

### Качество данных

Результаты анализа обучающей выборки:
- пропущенные значения — 0;
- полные дубликаты — 37;
- повторяющиеся тексты — 38;
- тексты с противоречивыми метками — 1.

Пересечения между выборками:
- Train / Validation — 4;
- Train / Test — 0;
- Validation / Test — 116.

Выявленные пересечения создают риск утечки данных между этапами настройки и оценки модели.

Исходные файлы сохранены без изменений. Очистка данных запланирована на следующих этапах проекта.

## 3. Рабочее окружение

Используется виртуальная машина Oracle VirtualBox с Ubuntu 24.04.5 LTS.

| Компонент | Версия |
|---|---|
| Ubuntu | 24.04.5 LTS |
| Python | 3.12.3 |
| pip (системный) | 24.0 |
| Git | 2.43.0 |
| Docker Engine | 29.9.3 |
| Docker Compose | 5.7.0 |
| JupyterLab | 4.6.5 |

Разработка выполняется под отдельным пользователем `mluser` без административных привилегий.

Для Python используется изолированное виртуальное окружение `.venv`.

## 4. Структура проекта

    ml-project/
    ├── data/
    ├── notebooks/
    │   └── 01_dataset_analysis.ipynb
    ├── src/
    ├── models/
    ├── tests/
    ├── security/
    │   ├── dataset_revision.txt
    │   ├── datasets.sha256
    │   ├── pip-audit.txt
    │   └── threat_model.md
    ├── requirements.txt
    ├── .gitignore
    └── README.md

Датасеты, модели, секреты и виртуальное окружение исключены из Git.

## 5. Воспроизведение окружения

### Системные зависимости

Требуется Linux, Python 3.12, Git и поддержка виртуальных окружений Python.

Для Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv
```

### Создание Python-окружения

Из каталога проекта:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Восстановление датасета

Исходные CSV-файлы не включаются в Git.

Для загрузки используется датасет S-Labs/prompt-injection-dataset и зафиксированная ревизия репозитория из `security/dataset_revision.txt`.

Скрипт загрузки будет размещен в `src/download_data.py`.

После загрузки проверить целостность:

```bash
sha256sum -c security/datasets.sha256
```

### Запуск JupyterLab

```bash
jupyter lab --no-browser --ip=127.0.0.1 --port=8888
```

Открыть Notebook:

`notebooks/01_dataset_analysis.ipynb`

При удаленном подключении рекомендуется использовать SSH-туннель, а не публиковать порт JupyterLab во внешней сети.

## 6. Реализованные меры безопасности

### Защита SSH

- создан отдельный пользователь `mluser`;
- настроена аутентификация по SSH-ключу ED25519;
- запрещен удаленный вход root;
- отключена парольная SSH-аутентификация;
- выполнена проверка конфигурации SSH.

### Firewall

Используется UFW:
- входящие соединения по умолчанию запрещены;
- исходящие соединения разрешены;
- SSH на порту 22 защищен правилом LIMIT;
- включено логирование high.

### Анализ сетевой поверхности

Проведен анализ слушающих портов командой `sudo ss -tulpn`.

Отключены ненужные для ML-проекта службы:
- Avahi;
- CUPS.

Оставлены необходимые службы SSH и локального DNS.

### Безопасность Python-зависимостей

Выполнены проверки:

```bash
python -m pip check
python -m pip_audit
```

Результаты:
- нарушений совместимости не обнаружено;
- известных уязвимостей на момент проверки не обнаружено.

Результат аудита сохранен в `security/pip-audit.txt`.

### Контроль целостности датасета

Для исходных файлов рассчитаны SHA256.

Эталонные контрольные суммы сохранены в `security/datasets.sha256` отдельно от каталога данных.

Проверка целостности всех трех CSV-файлов завершилась успешно.

Контрольная сумма позволяет обнаруживать изменения данных относительно сохраненного эталона, но не подтверждает достоверность источника.

## 7. Модель угроз

Мини-модель угроз представлена в файле:

`security/threat_model.md`

Рассмотрены:
- несанкционированный SSH-доступ;
- подмена датасета;
- утечка данных между выборками;
- утечка секретов из Git;
- уязвимости Python-зависимостей;
- обход ML-классификатора.

Для каждой угрозы определены последствия, контрмеры и статус реализации защиты.

## 8. Дальнейшее развитие

На следующих этапах планируется:

- устранение дубликатов и пересечений между выборками;
- обучение NLP-классификатора;
- оценка Precision, Recall и F1-score;
- исследование ложных отрицательных срабатываний;
- тестирование устойчивости модели к измененным prompt injection-запросам;
- разработка дополнительных механизмов защиты.

---

# Лабораторная работа №2

## Построение базовой ML-модели и проверка устойчивости входов

### 1. Цель работы

Разработка базовой модели обнаружения prompt injection-атак, оценка качества классификации, реализация валидации входных данных и проверка устойчивости модели к небольшим изменениям текстовых запросов.

### 2. Подготовка данных

Для обучения использован датасет S-Labs/prompt-injection-dataset из лабораторной работы №1.

Проведена очистка данных:
- устранены дубликаты;
- удалены записи с противоречивыми метками;
- устранены точные пересечения между выборками;
- исходные CSV-файлы сохранены без изменений.

| Выборка | До очистки | После очистки |
|---|---:|---:|
| Train | 11089 | 11050 |
| Validation | 2101 | 1981 |
| Test | 2101 | 2101 |

Всего исключено 159 объектов.

Подготовка выполняется скриптом:

```bash
python src/prepare_data.py
```

Контроль целостности:

```bash
sha256sum -c security/processed_datasets.sha256
```

### 3. Базовая ML-модель

Использован конвейер:

**TF-IDF + Logistic Regression**

Параметры:
- max_features = 30000;
- ngram_range = (1, 2);
- min_df = 2;
- sublinear_tf = True;
- C = 1.0;
- max_iter = 1000;
- class_weight = balanced;
- random_state = 42.

Обучение:

```bash
python src/train_model.py
```

Оценка:

```bash
python src/evaluate_model.py
```

### 4. Результаты оценки

| Метрика | Validation | Test |
|---|---:|---:|
| Accuracy | 97,83% | 95,53% |
| Precision (INJECTION) | 98,28% | 99,08% |
| Recall (INJECTION) | 97,13% | 91,91% |
| F1-score (INJECTION) | 97,70% | 95,36% |

Матрица ошибок на Test:

| Фактический класс | BENIGN | INJECTION |
|---|---:|---:|
| BENIGN | 1041 | 9 |
| INJECTION | 85 | 966 |

Основная метрика baseline — F1-score класса INJECTION.

Результаты сохранены в `metrics/baseline.json`.

### 5. Валидация входных данных

Реализован модуль `src/predict.py`.

Основные ограничения:
- вход — словарь с единственным полем text;
- значение text должно быть строкой;
- пустые строки отклоняются;
- максимальная длина текста — 2000 символов;
- нулевые байты запрещены;
- дополнительные и отсутствующие поля отклоняются.

Некорректные данные отклоняются до вызова ML-модели.

### 6. Автоматические тесты

Реализовано 9 автоматических тестов:
- 1 положительный;
- 8 негативных.

Все тесты завершились успешно.

Команда запуска:

```bash
python -m pytest tests/ -v
```

### 7. Эксперимент с устойчивостью

Исследованы 20 запросов:
- 10 BENIGN;
- 10 INJECTION.

Проверены изменения регистра, дополнительные пробелы и небольшие опечатки.

| Модификация | Доля изменившихся предсказаний |
|---|---:|
| Изменение регистра | 0% |
| Дополнительные пробелы | 0% |
| Опечатки | 0% |

Accuracy на выбранных объектах составила 95% до и после изменений.

Дополнительно проверен нетипичный повторяющийся запрос длиной 1079 символов. Система приняла его и классифицировала как BENIGN.

Результаты не доказывают устойчивость модели ко всем возможным атакам.

Запуск эксперимента:

```bash
python -m src.robustness_experiment
```

### 8. Статический анализ безопасности

Проведен анализ Python-модулей инструментом Bandit.

Первоначально обнаружены 3 замечания B101, связанные с использованием assert.

После замены assert явными проверками повторный анализ не выявил замечаний.

Команда:

```bash
python -m bandit -r src/
```

Результаты сохранены в `security/bandit_report.txt`.

### 9. Защита JupyterLab и модели

Реализованы следующие меры:
- JupyterLab привязан к 127.0.0.1:8888;
- удаленное подключение выполняется через SSH-туннель;
- API без аутентификации возвращает HTTP 403;
- каталог models имеет права 700;
- файл модели имеет права 600;
- контроль целостности модели выполняется с помощью SHA256;
- модель исключена из публичного Git-репозитория.

Артефакты joblib допускается загружать только из доверенного источника после проверки целостности.

### 10. Основные артефакты

- `notebooks/02_baseline_model.ipynb` — анализ и обучение;
- `src/prepare_data.py` — подготовка данных;
- `src/train_model.py` — обучение;
- `src/evaluate_model.py` — оценка модели;
- `src/predict.py` — валидация и предсказание;
- `src/robustness_experiment.py` — исследование устойчивости;
- `tests/test_predict.py` — автоматические тесты;
- `metrics/baseline.json` — итоговые метрики;
- `security/model.sha256` — контроль целостности модели.

Обученный артефакт модели сохраняется локально в `models/baseline_tfidf_logreg.joblib` и не включается в Git. Для его передачи преподавателю необходим отдельный доверенный канал или ссылка на артефакт.

### 11. Воспроизведение эксперимента

После создания Python-окружения и установки зависимостей:

```bash
python -m pip install -r requirements.txt
python src/download_data.py
python src/prepare_data.py
python src/train_model.py
python src/evaluate_model.py
python -m pytest tests/ -q
python -m src.robustness_experiment
python -m bandit -r src/
```

Все команды запускаются из корневого каталога проекта.

Модель и данные должны проходить контроль SHA256. Сохраненные joblib-файлы нельзя загружать из непроверенных источников.

### 12. Вывод

В рамках лабораторной работы построена воспроизводимая базовая NLP-модель обнаружения prompt injection-атак.

Модель достигла F1-score 95,36% на тестовой выборке. Реализованы проверки входных данных, автоматические тесты и меры защиты модели и среды выполнения.

Основным ограничением остается наличие 85 ложноотрицательных срабатываний на тестовой выборке. Для дальнейшего развития необходимо исследовать методы повышения полноты обнаружения атак и устойчивость к более сложным изменениям запросов.

---

# Лабораторная работа №3. Безопасный CI/CD для ML-проекта

## 1. Цель работы

Автоматизация контроля качества и безопасности ML-проекта с использованием GitHub Actions.

Реализован CI pipeline, который проверяет исходный код, зависимости, данные, качество модели и Docker-образ. При нарушении обязательных требований дальнейшее выполнение pipeline блокируется.

## 2. Используемые технологии

- Python 3.12
- GitHub Actions
- pytest
- Ruff
- Bandit
- pip-audit
- Docker
- Trivy 0.76.1
- scikit-learn
- SHA256

Версии Python-зависимостей зафиксированы в `requirements.txt`. Runtime-зависимости Docker вынесены в `requirements-runtime.txt`.

## 3. Последовательность CI/CD

Workflow: `.github/workflows/ci.yml`

Pipeline автоматически запускается при push в основные рабочие ветки и при pull request в main.

Последовательность этапов:

1. Checkout репозитория.
2. Настройка Python и установка зависимостей.
3. Получение модели из GitHub Release и проверка SHA256.
4. Проверка Ruff.
5. Статический анализ Bandit.
6. Запуск pytest.
7. Аудит зависимостей через pip-audit.
8. Проверка SHA256 контрольных данных.
9. Data Quality Gate.
10. Оценка кандидатной модели.
11. Model Quality Gate.
12. Сборка Docker-образа.
13. Проверка non-root и smoke-тест.
14. Сканирование образа и Dockerfile через Trivy.
15. Сохранение диагностических отчетов.

Обязательные проверки блокируют последующие этапы при ненулевом коде завершения. Диагностические отчеты сохраняются даже при сбое, а итоговый статус остается FAILED.

## 4. Контрольная выборка CI

Источник: S-Labs/prompt-injection-dataset.

Использована очищенная Validation-выборка из ЛР2.

Параметры:
- 200 объектов;
- 100 BENIGN;
- 100 INJECTION;
- random_state = 42;
- признаки: text и label.

Файл: `ci/fixtures/validation_200.csv`.

Происхождение, версия исходных данных, схема и SHA256 зафиксированы в `ci/fixture_manifest.json`.

Контроль целостности:

```bash
sha256sum -c ci/fixture.sha256
```

Независимая Test-выборка не используется для регулярной настройки CI.

## 5. Data Quality Gate

Реализация: `src/data_gate.py`.

Политика: `ci/data_policy.json`.

Проверяются:
- обязательные столбцы;
- структура и допустимые типы значений;
- количество объектов;
- отсутствие пропусков и пустых текстов;
- допустимые метки классов;
- распределение классов;
- отсутствие дубликатов текстов;
- максимальная длина текста;
- SHA256 контрольной выборки.

Запуск:

```bash
python -m src.data_gate
```

При успешной проверке возвращается exit code 0, при нарушении политики — exit code 1.

## 6. Model Quality Gate

Реализация: `src/model_gate.py`.

Эталон: `ci/baseline.json`.

Политика: `ci/model_policy.json`.

Основная метрика: F1-score класса INJECTION.

Baseline F1: 0.9746192893.

Допустимое относительное ухудшение: 5%.

Минимально допустимый F1:

0.9746192893 × 0.95 = 0.9258883249.

Кандидат проходит проверку, если:

candidate F1 >= 0.9258883249.

Дополнительно проверяются корректность метрики, количество объектов, версия контрольных данных и SHA256.

Эталон не перезаписывается результатами текущего запуска.

Команды:

```bash
python -m src.evaluate_ci_candidate
python -m src.model_gate
```

## 7. Автоматические тесты

Используется pytest.

Реализовано 14 тестов, включая проверки:
- допустимых и некорректных входов;
- ограничений длины;
- предобработки TF-IDF;
- расчета известных метрик;
- схемы контрольных данных;
- загрузки и предсказания сохраненной модели.

Запуск:

```bash
python -m pytest tests/ -q
```

Результат локальной проверки: 14 passed.

## 8. Статический анализ и аудит зависимостей

Команды:

```bash
ruff check src/ tests/
python -m bandit -r src/
python -m pip_audit -r requirements.txt
```

Политика pip-audit: любая известная уязвимость зависимости блокирует pipeline независимо от severity.

Секреты не требуются для получения публичного модельного артефакта. Права GITHUB_TOKEN ограничены чтением репозитория.

Секреты не должны передаваться заданиям, исполняющим недоверенный код.

## 9. Docker

Используется официальный Python-образ на основе Debian 13 Trixie.

Контейнер:
- запускается от пользователя UID 10001;
- содержит только необходимые runtime-зависимости;
- содержит проверяемый артефакт модели;
- не требует Docker socket или privileged mode.

Файл `.dockerignore` ограничивает контекст сборки.

Сборка:

```bash
docker build -t ml-project:lab3 .
```

Проверка пользователя:

```bash
docker run --rm --entrypoint id ml-project:lab3 -u
```

Ожидаемый UID: 10001.

Smoke-тест:

```bash
docker run --rm --network none --read-only --cap-drop=ALL --security-opt no-new-privileges ml-project:lab3
```

## 10. Сканирование Docker-образа

Используется Trivy 0.76.1.

Первоначально в образе на Debian 12 были обнаружены две критические уязвимости:
- CVE-2025-7458;
- CVE-2023-45853.

После перехода на Debian 13 Trixie повторное сканирование не обнаружило критических уязвимостей.

Проверка образа:

```bash
trivy image --scanners vuln --severity CRITICAL --exit-code 1 ml-project:lab3
```

Блокирующая политика проверки конфигурации:

```bash
trivy config --severity UNKNOWN,HIGH,CRITICAL --exit-code 1 Dockerfile
```

Замечание LOW об отсутствии HEALTHCHECK документировано: контейнер предназначен для однократного предсказания, а не для постоянно работающего сервиса.

Результаты Trivy зависят от актуальности базы уязвимостей. Ошибка сканирования не считается успешной проверкой.

## 11. Модель и проверка целостности

Модель опубликована отдельно от Git-репозитория:

https://github.com/DaniilLog/prompt-injection-detection-ml-security/releases/tag/model-v1.0.0

Файл: `baseline_tfidf_logreg.joblib`.

Перед загрузкой модели CI проверяет ее SHA256 по `security/model.sha256`.

Файлы joblib загружаются только из доверенных источников.

## 12. Демонстрация отказов CI

Для проверки работы механизмов блокировки созданы отдельные демонстрационные ветки.

| Сценарий | Ветка | Результат |
|---|---|---|
| Корректный pipeline | lab3-ci | SUCCESS |
| Нарушенная схема данных | lab3-demo-data | FAILED |
| Искусственное снижение F1 до 0.80 | lab3-demo-model | FAILED |
| Искусственная CRITICAL-находка | lab3-demo-security | FAILED |

Во всех демонстрациях использовались отдельные тестовые сценарии. Эталонная модель и исходные данные не изменялись.

В демонстрации Model Gate использованы искусственные метрики для проверки логики сравнения, а не результат оценки ухудшенной реальной модели.

В демонстрации Security Gate использован безопасный искусственный отчет. Реальное сканирование Trivy выполнялось отдельно.

Последующие обязательные этапы не выполнялись после отказа соответствующего gate.

Ссылки на конкретные GitHub Actions runs фиксируются в итоговом отчете.

## 13. Результат работы

Разработан автоматизированный CI pipeline для контроля качества и безопасности ML-проекта.

Обеспечены тестирование, статический анализ, аудит зависимостей, проверки качества данных и модели, защищенная сборка Docker и сканирование контейнера.

Получены успешный запуск и три отдельных сценария отказа.

Автоматическое развертывание в production не выполняется, поскольку не входит в обязательную часть лабораторной работы.

---

# Lab 4. Secure ML API and Monitoring

## Overview

The project provides a secure FastAPI service for
detecting prompt injection attempts using the
TF-IDF + Logistic Regression model from Lab 2.

Model version: lab2-v1.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | / | Web interface |
| GET | /health | Model readiness |
| POST | /predict | Protected prediction |
| GET | /metrics | Protected Prometheus metrics |

Prediction request:

    {"text": "What is machine learning?"}

Successful response:

    {
      "prediction": "BENIGN",
      "model_version": "lab2-v1",
      "request_id": "generated-uuid"
    }

## Security Controls

- Bearer authentication for /predict.
- Separate bearer authentication for /metrics.
- Maximum text length: 2000 characters.
- Maximum JSON body size: 32 KiB.
- Rate limiting: 10 requests per 60 seconds per IP.
- Server-side validation before model execution.
- Rejection of malformed JSON, null bytes and invalid types.
- SHA256 verification before model deserialization.
- Isolated ML worker with a 5-second inference timeout.
- Worker termination on inference timeout.
- Non-root Docker execution with UID 10001.
- Read-only container filesystem.
- Restricted Linux capabilities and process limits.
- No secrets or user input content in application logs.

HTTP error codes:

- 400: Malformed request.
- 401: Authentication failure.
- 413: Request body too large.
- 415: Unsupported media type.
- 422: Input validation failure.
- 429: Rate limit exceeded.
- 503: Service or worker unavailable.
- 504: Inference timeout.

## Local Execution

The application requires two environment variables:

- ML_API_TOKEN
- ML_METRICS_TOKEN

Secrets must be provided at runtime and must not
be committed to Git.

Run the application:

    python -m uvicorn src.api:app \
      --host 127.0.0.1 --port 8000 --workers 1

Open:

    http://127.0.0.1:8000/

## Docker

Build the image:

    docker build --pull -t ml-project:lab4 .

Run the container with runtime credentials:

    docker run -d --rm \
      --name ml-lab4 \
      --read-only \
      --cap-drop=ALL \
      --security-opt no-new-privileges \
      -p 127.0.0.1:8001:8000 \
      --env-file /path/to/private/lab4.env \
      ml-project:lab4

The environment file must be stored outside
the repository.

Verify non-root execution:

    docker run --rm --entrypoint id \
      ml-project:lab4 -u

Expected UID: 10001.

## Monitoring

Prometheus metrics are available at /metrics
with a separate authentication token.

Tracked metrics include:

- ml_api_requests_total
- ml_api_request_duration_seconds
- ml_api_rejections_total

Structured JSON logs contain:

- timestamp
- request_id
- route
- HTTP status
- request duration
- model version
- failure type

Input text and authentication tokens are not logged.

## Detection Scenario

A controlled scenario sends three requests
with invalid authentication tokens.

Detection condition:

3 or more HTTP 401 responses during
a 60-second observation interval.

Run:

    python -m src.detection_demo

Observed results:

- HTTP 401 counter before: 1
- HTTP 401 counter after: 4
- New authentication failures: 3
- Alert: TRIGGERED
- Recovery health: HTTP 200
- Recovery prediction: BENIGN

The report is stored in metrics/detection_demo.json.

This is a demonstration of detection logic,
not a continuously running alerting system.

## Limitations

The rate limiter stores counters in process memory.
Counters are reset after restart and are not shared
between workers.

IP-based limiting uses the direct connection address.
Forwarded headers are not trusted by the application.

The isolated model worker accepts one prediction
at a time. After an inference timeout, the worker
is terminated and readiness returns HTTP 503
until the service is restarted.

## Automated Verification

Run locally:

    ruff check src/ tests/
    python -m bandit -r src/
    python -m pytest tests/ -q
    python -m pip_audit -r requirements.txt
    python -m src.data_gate
    python -m src.model_gate
    python -m src.worker_smoke

GitHub Actions additionally verifies:

- Docker image build
- Non-root execution
- API health and prediction
- Authentication and input validation
- Protected metrics
- Trivy image vulnerability gate
- Trivy Dockerfile configuration gate

The dependency audit rejects known findings.
The Trivy image gate rejects CRITICAL vulnerabilities.
The Dockerfile gate rejects UNKNOWN, HIGH and
CRITICAL configuration findings.

## Security Scan Results

Local Trivy version: 0.76.1.

Scan date: November 5, 2026.

- CRITICAL image vulnerabilities: 0
- Blocking Dockerfile misconfigurations: 0
- Image gate exit code: 0
- Config gate exit code: 0

Reports are stored in the security/ directory.
