# ! front/Dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY required.txt .
RUN pip install --no-cache-dir -r required.txt

COPY docker/devcerts.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY front ./front
COPY favicon.ico .

ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "front.server.main:app", "--host", "0.0.0.0", "--port", "8005"]
