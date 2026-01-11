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
ENV FLASK_APP=app
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose port 5000
EXPOSE 5000

# Define volume for database persistence
VOLUME /app/instance

# Run gunicorn with 1 worker to ensure only one scheduler instance runs
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "app:create_app()"]
