# Python resmi imajını kullan - slim versiyonu daha küçük
FROM python:3.11-slim

# Çalışma dizinini belirle
WORKDIR /app

# Ortam değişkenlerini ayarla
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Sistem bağımlılıklarını yükle ve önbelleği temizle
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# requirements.txt dosyasını kopyala
COPY requirements.txt .

# Python paketlerini yükle
RUN pip install --no-cache-dir -r requirements.txt

# SQLite veritabanı için dizin oluştur
RUN mkdir -p /app/instance

# Önce veritabanı dosyasını kopyala
COPY instance/halisaha.db /app/instance/

# Sonra uygulama kodlarını kopyala
COPY . .

# Güvenlik için root olmayan kullanıcıya geç
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Uygulamayı çalıştır
CMD exec gunicorn --bind :$PORT \
    --workers 2 \
    --threads 8 \
    --timeout 0 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app 