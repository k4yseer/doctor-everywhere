# Use a slim Python image
FROM python:3.11-slim

# Set working directory and copy sources
WORKDIR /usr/src/app
COPY app/ ./app
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the service port and start Flask
EXPOSE 5009
ENV FLASK_APP=app.main
ENV PYTHONPATH=/usr/src/app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5009"]
