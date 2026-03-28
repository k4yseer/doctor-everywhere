FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/main.py .
COPY app/error_publisher.py .

EXPOSE 5015

CMD ["python", "main.py"]