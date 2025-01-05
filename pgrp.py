import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3
import dropbox
from dropbox.exceptions import AuthError

# Função para criar a tabela no banco de dados SQLite
def initialize_db():
    """Cria o banco de dados e a tabela de links se não existirem."""
    conn = sqlite3.connect("seen_links_pgrp.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS links (
        link TEXT PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()

# Função para conectar ao Dropbox
def connect_to_dropbox():
    try:
        dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
        print("Conectado ao Dropbox com sucesso.")
        return dbx
    except AuthError as e:
        print(f"Erro de autenticação no Dropbox: {e}")
        return None

# Função para subir o banco de dados para o Dropbox
def upload_db_to_dropbox(dbx):
    try:
        with open("seen_links_pgrp.db", "rb") as f:
            dbx.files_upload(f.read(), "/Apps/monitor_pgrp/seen_links_pgrp.db", mode=dropbox.files.WriteMode.overwrite)
        print("Banco de dados enviado para o Dropbox com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar o banco de dados para o Dropbox: {e}")

# Função para carregar links já vistos de um banco de dados SQLite
def load_seen_links(dbx):
    try:
        # Se o banco de dados não existir localmente, crie-o
        if not os.path.exists("seen_links_pgrp.db"):
            initialize_db()
        
        # Conectar ao banco de dados SQLite
        conn = sqlite3.connect('seen_links_pgrp.db')
        cursor = conn.cursor()

        # Carregar links já vistos
        cursor.execute("SELECT link FROM links")
        links = {row[0] for row in cursor.fetchall()}
        print(f"Links carregados do banco de dados: {links}")
        conn.close()
        return links
    except Exception as e:
        print(f"Erro ao carregar links do banco de dados: {e}")
        return set()

# Função para salvar os links no banco de dados SQLite
def save_seen_links(seen_links, dbx):
    try:
        # Conectar ao banco de dados SQLite
        conn = sqlite3.connect('seen_links_pgrp.db')
        cursor = conn.cursor()

        # Inserir novos links no banco de dados
        for link in seen_links:
            cursor.execute("INSERT OR IGNORE INTO links (link) VALUES (?)", (link,))
        
        conn.commit()
        conn.close()
        print("Banco de dados atualizado com novos links.")

        # Subir o banco de dados atualizado para o Dropbox
        upload_db_to_dropbox(dbx)
    except Exception as e:
        print(f"Erro ao salvar links no banco de dados: {e}")

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

# Configurações do e-mail
EMAIL_USER = os.getenv("EMAIL_USER")  # Recupera do Secret
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Recupera do Secret
TO_EMAIL = os.getenv("TO_EMAIL")  # Recupera do Secret

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal

# Configurações do Dropbox
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")  # Agora usa o access_token diretamente

# Função para buscar links de notícias da URL fornecida
def get_news_links(url):
    try:
        response = requests.get(url, verify=False)  # Ignora SSL
        if response.status_code != 200:
            print(f"Erro ao acessar a página: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = set()
        
        for a_tag in soup.find_all("a", href=True):
            if "news.jsf" in a_tag['href']:  # Apenas links de notícias relevantes
                full_link = f"https://www.pgdporto.pt/proc-web/{a_tag['href']}"
                links.add(full_link)
        
        print(f"Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"Erro ao buscar links: {e}")
        return set()

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
    dbx = connect_to_dropbox()
    if dbx is None:
        return

    seen_links = load_seen_links(dbx)
    current_links = get_news_links(URL)

    # Encontrando novos links que não foram vistos antes
    new_links = {link for link in current_links if link not in seen_links}

    if new_links:
        print(f"Novos links encontrados: {new_links}")
        for link in new_links:
            try:
                send_email_notification(get_article_content(link))
            except Exception as e:
                print(f"Erro ao enviar e-mail: {e}")

        # Atualiza o banco de dados após envio com os novos links
        seen_links.update(new_links)
        save_seen_links(seen_links, dbx)
    else:
        print("Nenhuma nova notícia para enviar e-mail.")

# Execução principal
if __name__ == "__main__":
    monitor_news()
