FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY error_service.py .

EXPOSE 5005

CMD ["python", "error_service.py"]