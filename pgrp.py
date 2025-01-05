import os
import dropbox
from dropbox.exceptions import AuthError
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sqlite3
import smtplib
import requests
import urllib3

# Configurações
BASE_URL = "https://www.pgdporto.pt/proc-web/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
DB_NAME = "seen_links_pgrp.db"
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")  # Agora usa o access_token diretamente
URL = f"{BASE_URL}"  # Página principal
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")

DROPBOX_PATH = f"/{DB_NAME}"

# Configurar warnings do urllib
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
def download_db_from_dropbox():
    """Faz o download do banco de dados do Dropbox."""
    try:
        dbx = get_dropbox_client()
        metadata, res = dbx.files_download(DROPBOX_PATH)
        with open(DB_NAME, "wb") as f:
            f.write(res.content)
        print("[DEBUG] Banco de dados baixado do Dropbox.")
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            print("[DEBUG] Banco de dados não encontrado no Dropbox. Criando um novo.")
        else:
            print(f"[ERRO] Falha ao baixar banco de dados: {e}")
            

# Função para enviar o banco de dados para o Dropbox
def upload_db_to_dropbox():
    """Faz o upload do banco de dados para o Dropbox."""
    try:
        dbx = get_dropbox_client()
        with open(DB_NAME, "rb") as f:
            dbx.files_upload(f.read(), DROPBOX_PATH, mode=dropbox.files.WriteMode("overwrite"))
        print("[DEBUG] Banco de dados enviado para o Dropbox.")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar banco de dados: {e}")

# Inicializa o banco de dados
def initialize_db():
    """Cria o banco de dados e a tabela de links."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_links_pgrp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT UNIQUE NOT NULL
    )
    """)
    conn.commit()
    conn.close()
    

# Função para carregar links já vistos do banco de dados
def load_seen_links_pgrp():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM seen_links_pgrp")
    links = {row[0] for row in cursor.fetchall()}
    conn.close()
    return seen_links_pgrp

# Função para salvar novos links no banco de dados
def save_seen_links_pgrp(new_links):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.executemany("INSERT OR IGNORE INTO seen_links_pgrp (link) VALUES (?)", [(link,) for link in new_links])
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

# Função para enviar uma notificação por e-mail
def send_email_notification(article_content):
    subject = "Novo comunicado da PGRP!"
    email_text = f"""\
From: {EMAIL_USER}
To: {TO_EMAIL}
Subject: {subject}
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit

{article_content}
"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, TO_EMAIL, email_text.encode("utf-8"))
        print("E-mail enviado com sucesso.")
    except Exception as e:
        print("Erro ao enviar e-mail:", e)

# Função para extrair texto mantendo a ordem, com formatação para listas
def extract_text_ordered(soup):
    content = []
    for element in soup.contents:
        if element.name == 'div':  # Para <div>
            content.append(element.get_text(strip=True))
        elif element.name == 'ul':  # Para listas não ordenadas
            for li in element.find_all('li', recursive=False):
                content.append(f"- {li.get_text(strip=True)}")
        elif element.name == 'ol':  # Para listas ordenadas
            for li in element.find_all('li', recursive=False):
                content.append(f"- {li.get_text(strip=True)}")
    return "\n".join(content)

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



# Função para obter conteúdo de um artigo a partir de seu link
def get_article_content(url):
    try:
        response = requests.get(url, verify=False)
        if response.status_code != 200:
            print(f"Erro ao acessar a notícia: {response.status_code}")
            return "Erro ao acessar a notícia."

        soup = BeautifulSoup(response.content, 'html.parser')

        title_elem = soup.find("div", class_="news-detail-title")
        title = title_elem.get_text(strip=True) if title_elem else "Título não encontrado."
        summary_elem = soup.find("div", class_="news-detail-summary")
        summary = " ".join(
            [elem.get_text(strip=True) for elem in summary_elem.find_all(["p", "div"], recursive=True)]
        ) if summary_elem else "Resumo não encontrado."
        body_elem = soup.find("div", class_="news-detail-body")
        body = extract_text_ordered(body_elem) if body_elem else "Conteúdo vazio."

        article_content = f"""
        {title}\n
        {summary}\n
        {body}
        """

        return article_content
    except Exception as e:
        print(f"Erro ao processar a notícia: {e}")
        return "Erro ao processar a notícia."

def monitor_news():
    """Monitora o site e envia notificações para novos links."""
    try:
        download_db_from_dropbox()  # Baixa o banco de dados antes de iniciar
    except Exception as e:
        print(f"[ERRO] Falha ao baixar banco de dados do Dropbox: {e}")
        initialize_db()  # Cria o banco se ele não existe

    initialize_db()  # Certifica-se de que o banco está pronto
    seen_links_pgrp = load_seen_links_pgrp()
    current_links = get_news_links(BASE_URL)

    # Encontrando novos links que não foram vistos antes
    new_links = set(current_links) - seen_links_pgrp

    if new_links:
        print(f"[DEBUG] Novos links: {new_links}")
        for link in new_links:
            try:
                article_content = get_article_content(link)
                send_email_notification(article_content)
            except Exception as e:
                print(f"[ERRO] Falha ao processar e enviar notificação para o link {link}: {e}")

        save_seen_links_pgrp(new_links)
    else:
        print("[DEBUG] Nenhum novo link encontrado.")

    try:
        upload_db_to_dropbox()  # Envia o banco de dados atualizado para o Dropbox
    except Exception as e:
        print(f"[ERRO] Falha ao enviar banco de dados para o Dropbox: {e}")


# Execução principal
if __name__ == "__main__":
    monitor_news()
