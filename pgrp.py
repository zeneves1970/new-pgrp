import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import smtplib
import dropbox
from dropbox.exceptions import AuthError

# Configurações
DB_NAME = "seen_links_pgrp.db"
EMAIL_USER = os.getenv("EMAIL_USER")  # Recupera do Secret
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Recupera do Secret
TO_EMAIL = os.getenv("TO_EMAIL")  # Recupera do Secret
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")  # Agora usa o access_token diretamente
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal

# Função para criar a tabela no banco de dados SQLite
def initialize_db():
    """Cria o banco de dados e a tabela de links se não existirem."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS links (
        link TEXT PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()
    print(f"[DEBUG] Banco de dados '{DB_NAME}' e tabela 'links' criados/verificados com sucesso.")

# Garante que o banco de dados e a tabela existem antes de qualquer operação
def ensure_table_exists():
    """Verifica se a tabela 'links' existe e a cria caso contrário."""
    if not os.path.exists(DB_NAME):
        print(f"[DEBUG] Banco de dados '{DB_NAME}' não encontrado localmente. Criando um novo.")
        initialize_db()
    else:
        print(f"[DEBUG] Banco de dados '{DB_NAME}' encontrado. Verificando tabela 'links'.")
        initialize_db()  # Garante que a tabela existe no banco existente

# Função para conectar ao Dropbox
def connect_to_dropbox():
    try:
        dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
        print("[DEBUG] Conectado ao Dropbox com sucesso.")
        return dbx
    except AuthError as e:
        print(f"[ERRO] Erro de autenticação no Dropbox: {e}")
        return None

# Função para baixar o banco de dados do Dropbox
def download_db_from_dropbox(dbx):
    try:
        metadata, res = dbx.files_download(f"/{DB_NAME}")
        with open(DB_NAME, "wb") as f:
            f.write(res.content)
        print("[DEBUG] Banco de dados baixado do Dropbox com sucesso.")
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            print("[DEBUG] Banco de dados não encontrado no Dropbox. Criando um novo localmente.")
            initialize_db()
        else:
            print(f"[ERRO] Falha ao baixar banco de dados: {e}")

# Função para subir o banco de dados para o Dropbox
def upload_db_to_dropbox(dbx):
    try:
        with open(DB_NAME, "rb") as f:
            dbx.files_upload(f.read(), f"/{DB_NAME}", mode=dropbox.files.WriteMode.overwrite)
        print("[DEBUG] Banco de dados enviado para o Dropbox com sucesso.")
    except Exception as e:
        print(f"[ERRO] Erro ao enviar o banco de dados para o Dropbox: {e}")

# Função para carregar links já vistos do banco de dados
def load_seen_links():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM links")
    links = {row[0] for row in cursor.fetchall()}
    conn.close()
    print(f"[DEBUG] Links carregados do banco de dados: {links}")
    return links

# Função para salvar novos links no banco de dados
def save_seen_links(seen_links):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.executemany("INSERT OR IGNORE INTO links (link) VALUES (?)", [(link,) for link in seen_links])
    conn.commit()
    conn.close()
    print("[DEBUG] Banco de dados atualizado com novos links.")

# Função para buscar links de notícias da URL fornecida
def get_news_links(url):
    try:
        response = requests.get(url, verify=False)  # Ignora SSL
        if response.status_code != 200:
            print(f"[ERRO] Erro ao acessar a página: {response.status_code}")
            return set()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = set()
        for a_tag in soup.find_all("a", href=True):
            if "news.jsf" in a_tag['href']:  # Apenas links de notícias relevantes
                full_link = f"{BASE_URL}{a_tag['href']}"
                links.add(full_link)
        
        print(f"[DEBUG] Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"[ERRO] Falha ao buscar links: {e}")
        return set()

# Função para obter o conteúdo de um artigo
def get_article_content(url):
    try:
        response = requests.get(url, verify=False)
        if response.status_code != 200:
            print(f"[ERRO] Erro ao acessar a notícia: {response.status_code}")
            return "Erro ao acessar a notícia."

        soup = BeautifulSoup(response.content, 'html.parser')

        title_elem = soup.find("div", class_="news-detail-title")
        title = title_elem.get_text(strip=True) if title_elem else "Título não encontrado."
        summary_elem = soup.find("div", class_="news-detail-summary")
        summary = summary_elem.get_text(strip=True) if summary_elem else "Resumo não encontrado."
        body_elem = soup.find("div", class_="news-detail-body")
        body = body_elem.get_text(strip=True) if body_elem else "Conteúdo vazio."

        return f"{title}\n\n{summary}\n\n{body}"
    except Exception as e:
        print(f"[ERRO] Falha ao processar a notícia: {e}")
        return "Erro ao processar a notícia."

# Função para enviar uma notificação por e-mail
def send_email_notification(content):
    subject = "Novo comunicado da PGRP!"
    email_text = f"""\
From: {EMAIL_USER}
To: {TO_EMAIL}
Subject: {subject}
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit

{content}
"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, TO_EMAIL, email_text.encode("utf-8"))
        print("[DEBUG] E-mail enviado com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar e-mail: {e}")

# Função principal de monitoramento
def monitor_news():
    ensure_table_exists()  # Garante que o banco de dados e a tabela existem
    dbx = connect_to_dropbox()
    if not dbx:
        return

    download_db_from_dropbox(dbx)  # Baixa o banco de dados do Dropbox

    seen_links = load_seen_links()
    current_links = get_news_links(URL)

    new_links = current_links - seen_links
    if new_links:
        print(f"[DEBUG] Novos links encontrados: {new_links}")
        for link in new_links:
            content = get_article_content(link)
            send_email_notification(content)
        save_seen_links(new_links)  # Atualiza o banco localmente
        upload_db_to_dropbox(dbx)  # Envia o banco de dados atualizado para o Dropbox
    else:
        print("[DEBUG] Nenhuma nova notícia para enviar.")

# Execução principal
if __name__ == "__main__":
    monitor_news()
