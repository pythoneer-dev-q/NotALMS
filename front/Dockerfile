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
# запускаем модуль, а не uvicorn напрямую: host/port/ssl берутся из env (FRONT_HOST/FRONT_PORT/SSL_*)
CMD ["python", "-m", "front.server.main"]
