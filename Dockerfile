# Base image Python
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy file requirements trước để cache
COPY requirements.txt requirements.txt

# Cài dependency
RUN pip install -r requirements.txt

# Copy toàn bộ code backend vào container
COPY . .

# Expose port
ENV PORT=5000

# Lệnh chạy gunicorn
CMD ["gunicorn", "-b", ":5000", "app:app"]
