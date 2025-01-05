import os
import requests
import sqlite3
from bs4 import BeautifulSoup
import smtplib
import urllib3
import dropbox
from dropbox.exceptions import AuthError

# Função para inicializar o banco de dados
def initialize_db():
    """Cria o banco de dados e a tabela de links se não existirem."""
    conn = sqlite3.connect("seen_links.db")
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
        dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))
        print("Conectado ao Dropbox com sucesso.")
        return dbx
    except AuthError as e:
        print(f"Erro de autenticação no Dropbox: {e}")
        return None

# Função para baixar o banco de dados SQLite do Dropbox
def download_db_from_dropbox(dbx):
    try:
        with open("seen_links.db", "wb") as f:
            metadata, res = dbx.files_download(path="/seen_links.db")
            f.write(res.content)
        print("Banco de dados baixado com sucesso.")
    except Exception as e:
        print(f"Erro ao baixar banco de dados: {e}")

# Função para carregar links já vistos do banco de dados
def load_seen_links():
    """Carrega links do banco de dados SQLite."""
    conn = sqlite3.connect('seen_links.db')
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM links")
    links = {row[0] for row in cursor.fetchall()}
    conn.close()
    return links

# Função para salvar links no banco de dados SQLite
def save_seen_links(seen_links, dbx):
    try:
        conn = sqlite3.connect('seen_links.db')
        cursor = conn.cursor()

        for link in seen_links:
            cursor.execute("INSERT OR IGNORE INTO links (link) VALUES (?)", (link,))
        
        conn.commit()
        conn.close()
        print("Banco de dados atualizado com novos links.")

        # Subir o banco de dados atualizado para o Dropbox
        upload_db_to_dropbox(dbx)
    except Exception as e:
        print(f"Erro ao salvar links no banco de dados: {e}")

# Função para enviar notificação por e-mail
def send_email_notification(article_content):
    subject = "Novo comunicado da PGRP!"
    email_text = f"""\
From: {os.getenv("EMAIL_USER")}
To: {os.getenv("TO_EMAIL")}
Subject: {subject}
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit

{article_content}
"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
            server.sendmail(os.getenv("EMAIL_USER"), os.getenv("TO_EMAIL"), email_text.encode("utf-8"))
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

# Função para extrair texto formatado para listas
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

def monitor_news():
    dbx = connect_to_dropbox()
    if dbx is None:
        return

    # Se o banco de dados não existir, baixe-o
    if not os.path.exists("seen_links.db"):
        download_db_from_dropbox(dbx)

    # Carregar links já vistos e buscar os links das notícias
    seen_links = load_seen_links()
    current_links = get_news_links("https://www.pgdporto.pt/proc-web/")

    # Encontrando novos links
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
    initialize_db()  # Inicializa o banco de dados e tabela
    monitor_news()
