# rasa/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Rasa project
COPY . .

# Train the model
RUN rasa train

# Expose ports
EXPOSE 5005

# Run Rasa
CMD ["rasa", "run", "--enable-api", "--port", "5005"]