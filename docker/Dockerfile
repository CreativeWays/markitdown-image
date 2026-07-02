FROM python:3.12-slim

# ffmpeg is required for the audio-transcription extra
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "markitdown[all]" \
    markitdown-ocr \
    openai \
    fastapi \
    "uvicorn[standard]" \
    python-multipart

WORKDIR /app
COPY app.py /app/app.py

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
