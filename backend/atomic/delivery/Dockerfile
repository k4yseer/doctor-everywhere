FROM python:3.11-slim
 
WORKDIR /usr/src/app
COPY app/ ./app
COPY requirements.txt ./
 
RUN pip install --no-cache-dir -r requirements.txt
 
EXPOSE 5014
 
ENV FLASK_APP=app.main
ENV PYTHONPATH=/usr/src/app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5014"]