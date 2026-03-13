FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy knowledge base for in-memory loading
COPY test_knowledgebase/ /app/test_knowledgebase/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
