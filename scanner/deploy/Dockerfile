FROM python:3.13-slim
RUN useradd --create-home --uid 1000 scanner
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=scanner:scanner scanner /app/scanner
COPY --chown=scanner:scanner models /app/models
USER scanner
ENV SCANNER_DEVICE=cpu SCANNER_REQUIRE_TOKEN=true \
    SCANNER_SELECTION=/app/models/selection.json \
    SCANNER_DETECTOR=/app/models/detector.pt \
    SCANNER_CLASSIFIER=/app/models/classifier.pt
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "scanner.service:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
