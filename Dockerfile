FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV HOST=0.0.0.0
EXPOSE 8350

CMD ["python3", "run.py"]
