FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pydevd-pycharm

COPY . .

ENV PORT 8080
ENV DEBUG_PORT 5678
ENV DEBUG_HOST host.docker.internal

CMD ["sh", "-c", "if [ \"$REMOTE_DEBUG\" = \"true\" ]; then python -Xfrozen_modules=off debug.py; else exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 4; fi"]
