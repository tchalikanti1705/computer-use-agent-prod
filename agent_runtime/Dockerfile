FROM python:3.12-slim
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ shared/
COPY control_plane/ control_plane/
COPY agent_runtime/ agent_runtime/
CMD ["python", "-m", "agent_runtime.worker"]
