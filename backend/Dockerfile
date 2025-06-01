FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY server.py .
COPY prompts.py .
COPY tools.py .

# Expose WebSocket port
EXPOSE 9082

# Run the WebSocket server
CMD ["python", "server.py"]
