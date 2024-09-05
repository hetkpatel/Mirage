# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD wsgi.py /app
ADD embedding_models /app/embedding_models
ADD tools /app/tools
ADD .env /app
ADD requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=wsgi.py
ENV FLASK_RUN_HOST=0.0.0.0