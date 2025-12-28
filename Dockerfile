# Usamos una versión estable de Python
FROM python:3.11-slim

# Instalar herramientas básicas del sistema
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    --no-install-recommends

# Instalar Google Chrome de forma más segura
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos
COPY . .

# Instalar librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Puerto para Render
EXPOSE 10000

# Comando para arrancar
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
