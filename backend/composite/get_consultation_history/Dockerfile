FROM python:3.13-slim

WORKDIR /usr/src/app
COPY app/ ./app
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5013
# ENV FLASK_APP=app.main
ENV PYTHONPATH=/usr/src/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5013"]
