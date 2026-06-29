# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV PORT=8080

# Set work directory
WORKDIR /app

# NEW: Install curl, Node.js, and npm so Python can execute `npx` commands
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the app using uvicorn
CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8080"]