import os
import requests
from bs4 import BeautifulSoup
import smtplib
import sqlite3
import urllib3

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
DB_FILE = "seen_links_pgrp.db"  # Banco de dados SQLite

# Função para inicializar a tabela no banco de dados
def initialize_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Criar tabela se não existir
        c.execute('''CREATE TABLE IF NOT EXISTS seen_links (link TEXT UNIQUE)''')
        conn.commit()
        conn.close()
        print("Banco de dados inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")

# Função para carregar links já vistos do banco de dados
def load_seen_links():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT link FROM seen_links")
        seen_links = {row[0] for row in c.fetchall()}
        conn.close()
        print(f"Links carregados do banco de dados: {seen_links}")
        return seen_links
    except Exception as e:
        print(f"Erro ao carregar links do banco de dados: {e}")
    return set()

# Função para salvar os links já vistos no banco de dados
def save_seen_links(seen_links):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Apagar todos os links existentes na tabela
        c.execute("DELETE FROM seen_links")
        # Inserir os links novos
        for link in seen_links:
            c.execute("INSERT INTO seen_links (link) VALUES (?)", (link,))
        conn.commit()
        conn.close()
        print("Banco de dados atualizado com links novos.")
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
    """
    Função para buscar links de notícias da URL fornecida.
    Retorna uma lista com os links completos encontrados.
    """
    try:
        response = requests.get(url, verify=False)  # Ignora SSL
        if response.status_code != 200:
            print(f"Erro ao acessar a página: {response.status_code}")
            return []
        
        # Parse da resposta com BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        links = set()
        
        # Ajuste para criar a URL completa
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

        # Extrair título
        title_elem = soup.find("div", class_="news-detail-title")
        title = title_elem.get_text(strip=True) if title_elem else "Título não encontrado."

        # Extrair resumo
        summary_elem = soup.find("div", class_="news-detail-summary")
        summary = " ".join(
            [elem.get_text(strip=True) for elem in summary_elem.find_all(["p", "div"], recursive=True)]
        ) if summary_elem else "Resumo não encontrado."

        # Extrair corpo da notícia
        body_elem = soup.find("div", class_="news-detail-body")
        body = extract_text_ordered(body_elem) if body_elem else "Conteúdo vazio."

        # Montar o conteúdo final do e-mail
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

    # Encontrando novos links que não foram vistos antes
    new_links = {link for link in current_links if link not in seen_links}

    if new_links:
        print(f"Novos links encontrados: {new_links}")
        for link in new_links:
            try:
                # Envia e-mail apenas para novos links
                send_email_notification(get_article_content(link))
            except Exception as e:
                print(f"Erro ao enviar e-mail: {e}")

        # Atualiza a cache após envio com os novos links
        seen_links.update(new_links)
        save_seen_links(seen_links)
    else:
        print("Nenhuma nova notícia para enviar e-mail.")


# Execução principal
if __name__ == "__main__":
    # Inicializa o banco de dados e a tabela
    initialize_db()
    monitor_news()
