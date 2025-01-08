# Base image
FROM python:3.9-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Environment variables
ENV PORT=8080

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
RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

# Port'u belirt
EXPOSE ${PORT}

# Uygulamayı başlat
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app 

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