# Use imagem base leve do Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia os arquivos de dependências primeiro para melhor cache
COPY requirements.txt .

# Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do projeto para dentro do container
COPY . .

# (Opcional) Se você usar variáveis de ambiente via .env:
# RUN pip install python-dotenv

# Comando padrão para rodar o gerador
CMD ["python", "report_generator.py"]