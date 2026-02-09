# Use official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV WORKERS=1

# Expose port (using ARG for build-time configuration)
ARG PORT=5000
EXPOSE ${PORT}

# Define volume for database persistence
VOLUME /app/instance

# Run gunicorn - using shell form to allow variable substitution
CMD gunicorn -w ${WORKERS} -b 0.0.0.0:${PORT} "app:create_app()"
