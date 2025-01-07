import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import smtplib
import dropbox
from dropbox.exceptions import AuthError

# Configurações
DB_NAME = "seen_links_pgrp.db"
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
APP_KEY = os.getenv("DROPBOX_APP_KEY")  # Usando variáveis de ambiente
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")  # Usando variáveis de ambiente
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"

# Inicializa o banco de dados local
def initialize_db():
    # Verifica se a tabela já existe
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                link TEXT PRIMARY KEY
            )
        """)
        conn.commit()
    print("[INFO] Banco de dados local inicializado.")

# Verifica se o banco de dados existe no Dropbox
def check_db_exists_in_dropbox(dbx):
    try:
        dbx.files_get_metadata(f"/{DB_NAME}")
        print("[DEBUG] Banco de dados encontrado no Dropbox.")
        return True
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            print("[INFO] Banco de dados não encontrado no Dropbox.")
            return False
        else:
            print(f"[ERRO] Erro ao verificar banco no Dropbox: {e}")
            return False

# Faz o download do banco do Dropbox
def download_db_from_dropbox(dbx):
    try:
        metadata, res = dbx.files_download(f"/{DB_NAME}")
        with open(DB_NAME, "wb") as f:
            f.write(res.content)
        print("[DEBUG] Banco de dados baixado do Dropbox com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao baixar banco de dados: {e}")

# Faz upload do banco para o Dropbox
def upload_db_to_dropbox(dbx):
    try:
        with open(DB_NAME, "rb") as f:
            dbx.files_upload(
                f.read(),
                f"/{DB_NAME}",
                mode=dropbox.files.WriteMode.overwrite,
                mute=True
            )
        print("[DEBUG] Banco de dados enviado para o Dropbox com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar banco de dados: {e}")

# Carrega links já vistos
def load_seen_links():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM links")
        links = {row[0] for row in cursor.fetchall()}
    print(f"[DEBUG] Links carregados do banco de dados: {links}")
    return links

# Salva novos links no banco
def save_seen_links(seen_links):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.executemany("INSERT OR IGNORE INTO links (link) VALUES (?)", [(link,) for link in seen_links])
        conn.commit()
    print("[DEBUG] Banco de dados atualizado com novos links.")

# Obtém links de notícias
def get_news_links(url):
    try:
        response = requests.get(url, verify=False)
        if response.status_code != 200:
            print(f"[ERRO] Erro ao acessar a página: {response.status_code}")
            return set()
        soup = BeautifulSoup(response.content, 'html.parser')
        links = {f"{BASE_URL}{a['href']}" for a in soup.find_all("a", href=True) if "news.jsf" in a['href']}
        print(f"[DEBUG] Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"[ERRO] Falha ao buscar links: {e}")
        return set()

# Envia notificação por e-mail
def send_email_notification(content):
    subject = "Novo comunicado da PGRP!"
    email_text = f"""\
From: {EMAIL_USER}
To: {TO_EMAIL}
Subject: {subject}
Content-Type: text/plain; charset=utf-8

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

# Função para obter um novo access token usando o refresh token
def get_access_token_using_refresh_token(refresh_token, app_key, app_secret):
    url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret
    }

    response = requests.post(url, data=data)

    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"]
    else:
        print(f"[ERRO] Falha ao obter novo access token: {response.status_code} - {response.text}")
        return None

# Conectar ao Dropbox usando o refresh_token
def connect_to_dropbox(refresh_token, app_key, app_secret):
    # Obtém o access_token usando o refresh_token
    access_token = get_access_token_using_refresh_token(refresh_token, app_key, app_secret)

    if access_token:
        try:
            # Inicializa a conexão com o Dropbox usando o novo access token
            dbx = dropbox.Dropbox(access_token)
            print("[DEBUG] Conexão com o Dropbox realizada com sucesso.")
            return dbx
        except AuthError as e:
            print(f"[ERRO] Erro de autenticação no Dropbox: {e}")
            return None
    else:
        print("[ERRO] Não foi possível obter o access token.")
        return None

# Monitoramento principal
def monitor_news():
    dbx = connect_to_dropbox(DROPBOX_REFRESH_TOKEN, APP_KEY, APP_SECRET)  # Usando variáveis de ambiente
    if not dbx:
        return

    if not check_db_exists_in_dropbox(dbx):
        # Banco de dados não encontrado no Dropbox, cria localmente e envia
        initialize_db()  # Garantir que a tabela seja criada, caso não exista
        upload_db_to_dropbox(dbx)
    else:
        # Banco de dados encontrado, baixa para local
        download_db_from_dropbox(dbx)

    # Continua com a lógica de monitoramento
    seen_links = load_seen_links()
    current_links = get_news_links(URL)

    new_links = current_links - seen_links
    if new_links:
        print(f"[DEBUG] Novos links encontrados: {new_links}")
        for link in new_links:
            send_email_notification(link)
        save_seen_links(new_links)
        upload_db_to_dropbox(dbx)
    else:
        print("[DEBUG] Nenhuma nova notícia para enviar.")

# Execução principal
if __name__ == "__main__":
    monitor_news()

