# Docker image for the online backend (Render.com free web service)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user app ./app
# the app writes temp files / local backups here – owned by the app user (Render runs as "user")
RUN mkdir -p /home/user/app/storage && chown -R user:user /home/user/app
USER user
# Render gives the port in $PORT
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips '*' --timeout-keep-alive 75"]
