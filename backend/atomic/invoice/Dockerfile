FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 5008
CMD ["python", "app/main.py"]
