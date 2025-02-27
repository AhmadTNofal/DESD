# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies including pkg-config, mysql client dev libraries and gcc
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    gcc

# Copy requirements file and install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy all project files into the container
COPY . /app/

# Collect static files for Django
RUN python manage.py collectstatic --noinput

# Run the application using gunicorn
CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000"]
