# use a slim Python image
FROM python:3.11-slim

# set workdir and copy sources
WORKDIR /usr/src/app
COPY app/ ./app
COPY requirements.txt ./

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# expose port and start the service
EXPOSE 5000
ENV FLASK_APP=app.main
ENV PYTHONPATH=/usr/src/app
CMD ["flask", "run", "--host=0.0.0.0"]