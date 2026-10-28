FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/analytics-consumer/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY services/analytics-consumer/main.py ./main.py

USER 10001:10001

CMD ["python", "-u", "main.py"]
