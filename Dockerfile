# Base image olarak Python 3.9 kullan
FROM python:3.9-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY . .

# Non-root kullanıcı oluştur
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Port'u ortam değişkeninden al
ENV PORT=8080

# Health check tanımla
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Uygulamayı başlat
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app 

# MongoDB bağlantısı için gerekli paketleri ekleyelim
RUN apt-get update && apt-get install -y \
    python3-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# MongoDB sertifikalarını ekleyelim  
RUN mkdir -p /etc/ssl/certs
COPY certificates/mongodb.crt /etc/ssl/certs/

# Environment variables
ENV MONGO_URI="mongodb+srv://ae52:Erenemir1comehacker@cluster0.y5nv8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
ENV DB_NAME="halisaha_db" 