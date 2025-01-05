import os
import requests
import sqlite3
import smtplib
import dropbox
from bs4 import BeautifulSoup

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


# Configurações do e-mail
EMAIL_USER = os.getenv("EMAIL_USER")  # Recupera do Secret
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Recupera do Secret
TO_EMAIL = os.getenv("TO_EMAIL")  # Recupera do Secret

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal

# Configuração do Dropbox (token de acesso)
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")  # Token do Dropbox
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Nome do arquivo SQLite no Dropbox
DB_FILE_PATH = "/seen_links.db"  # O caminho no Dropbox

# Função para criar e inicializar o banco de dados SQLite no Dropbox
def init_db():
    try:
        # Verifica se o banco de dados já existe no Dropbox
        try:
            dbx.files_download(DB_FILE_PATH)
            print("Banco de dados encontrado no Dropbox.")
        except dropbox.exceptions.ApiError:
            # Se não existir, cria o banco de dados e envia para o Dropbox
            conn = sqlite3.connect("/tmp/seen_links.db")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_links (
                    link TEXT PRIMARY KEY
                )
            """)
            conn.commit()
            conn.close()

            # Envia o arquivo para o Dropbox
            with open("/tmp/seen_links.db", "rb") as f:
                dbx.files_upload(f.read(), DB_FILE_PATH, mode=dropbox.files.WriteMode("overwrite"))
            print("Banco de dados criado e enviado para o Dropbox.")
    except Exception as e:
        print(f"Erro ao inicializar o banco de dados: {e}")

# Função para verificar links no banco de dados
def load_seen_links():
    seen_links = set()
    try:
        # Baixa o arquivo de banco de dados do Dropbox
        metadata, res = dbx.files_download(DB_FILE_PATH)
        with open("/tmp/seen_links.db", "wb") as f:
            f.write(res.content)

        # Conecta ao banco de dados SQLite
        conn = sqlite3.connect("/tmp/seen_links.db")
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM seen_links")
        seen_links = {row[0] for row in cursor.fetchall()}
        conn.close()
        print(f"Links carregados do banco de dados: {seen_links}")
    except Exception as e:
        print(f"Erro ao carregar links do banco de dados: {e}")
    
    return seen_links

# Função para salvar os links no banco de dados
def save_seen_links(seen_links):
    try:
        # Baixa o arquivo de banco de dados do Dropbox
        metadata, res = dbx.files_download(DB_FILE_PATH)
        with open("/tmp/seen_links.db", "wb") as f:
            f.write(res.content)

        # Conecta ao banco de dados SQLite
        conn = sqlite3.connect("/tmp/seen_links.db")
        cursor = conn.cursor()

        # Insere novos links no banco de dados
        for link in seen_links:
            cursor.execute("INSERT OR IGNORE INTO seen_links (link) VALUES (?)", (link,))
        conn.commit()
        conn.close()

        # Envia o arquivo de volta para o Dropbox
        with open("/tmp/seen_links.db", "rb") as f:
            dbx.files_upload(f.read(), DB_FILE_PATH, mode=dropbox.files.WriteMode("overwrite"))
        print("Banco de dados atualizado com novos links.")
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

# Função para buscar links de notícias da URL fornecida
def get_news_links(url):
    try:
        response = requests.get(url, verify=False)  # Ignora SSL
        if response.status_code != 200:
            print(f"Erro ao acessar a página: {response.status_code}")
            return []

        # Parse da resposta com BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        links = set()

        for a_tag in soup.find_all("a", href=True):
            if "news.jsf" in a_tag['href']:  # Apenas links de notícias relevantes
                full_link = f"https://www.pgdporto.pt/proc-web/{a_tag['href']}"  # Monta a URL completa
                links.add(full_link)

        print(f"Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"Erro ao buscar links: {e}")
        return set()

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
    seen_links = load_seen_links()
    current_links = get_news_links(URL)

    new_links = {link for link in current_links if link not in seen_links}

    if new_links:
        print(f"Novos links encontrados: {new_links}")
        for link in new_links:
            try:
                send_email_notification(get_article_content(link))
            except Exception as e:
                print(f"Erro ao enviar e-mail: {e}")

        seen_links.update(new_links)
        save_seen_links(seen_links)
    else:
        print("Nenhuma nova notícia para enviar e-mail.")

# Execução principal
if __name__ == "__main__":
    init_db()  # Inicializa o banco de dados
    monitor_news()
