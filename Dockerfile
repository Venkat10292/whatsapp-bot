# Use Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy everything into the container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for the Flask app
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
