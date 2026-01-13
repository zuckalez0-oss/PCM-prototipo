# Usa uma imagem leve do Python
FROM python:3.10-slim

# Evita que o Python grave arquivos .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema (necessário para alguns pacotes Python e Banco de Dados)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para dentro do container
COPY . .

# Expõe a porta que usaremos (apenas informativo)
EXPOSE 8000

# Comando para rodar a aplicação usando Gunicorn
# IMPORTANTE: Troque 'nome_do_projeto' pelo nome da pasta onde está seu settings.py
CMD ["gunicorn", "--bind", "0.0.0.0:8000", ".wsgi:application"]
