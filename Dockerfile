# Use official Python slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required by Python libraries and OCR
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    gcc \
    libssl-dev \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-dev \
    libgl1 \
    poppler-utils \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy app files into container
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip

# Ensure only official SmartAPI is used
RUN pip uninstall -y angel-one-smartapi || true
RUN pip install smartapi-python==1.4.8

# Install other requirements
RUN pip install -r requirements.txt

# Expose Flask port
EXPOSE 5000

# Start the Flask app
CMD ["python", "app.py"]
