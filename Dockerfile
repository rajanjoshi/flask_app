# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app
COPY app.py .

# Expose port
EXPOSE 8080

# Start app
CMD ["python", "app.py"]
