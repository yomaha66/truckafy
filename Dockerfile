FROM python:3.11-slim
# ffmpeg (Debian build includes librubberband), plus libs numpy/scipy wheels need
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py mix.py eleven.py script.py ./
COPY assets/ ./assets/
RUN python -c "import mix, script; print('ok')"
ENV PORT=8080 PYTHONUNBUFFERED=1
CMD exec gunicorn --bind :$PORT --workers 2 --threads 2 --timeout 300 main:app
