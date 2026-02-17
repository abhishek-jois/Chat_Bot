FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV DATA_DIR=/app/data
ENV USE_GOOGLE_SHEETS=false

# Run the application
CMD ["python", "backend/main.py"]
