# Use an official, lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /usr/src/app

# Set environment variables for better Python execution in Docker
# Prevents Python from writing .pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1 
# Ensures output is logged immediately (crucial for catching errors in Docker)
ENV PYTHONUNBUFFERED=1 

# Copy just the requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies without storing cache to keep the image size small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application code into the container
COPY ./app ./app

# Expose the port your wrapper runs on (matching your .env)
EXPOSE 5008

# Command to run the service
CMD ["python", "app/main.py"]