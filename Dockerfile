FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install requirements
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# If you use config.py, copy it in yourself, or mount it as a volume
# Or set env vars and use dotenv in your code

CMD ["python", "main.py"]
