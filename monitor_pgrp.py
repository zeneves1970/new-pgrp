import os
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurações do e-mail a partir de variáveis de ambiente
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal
SEEN_LINKS_FILE = "seen_links.txt"  # Nome do arquivo para armazenar links já vistos


# Função para carregar links já vistos de um arquivo
def load_seen_links():
    if os.path.exists(SEEN_LINKS_FILE) and os.path.getsize(SEEN_LINKS_FILE) > 0:
        with open(SEEN_LINKS_FILE, "r") as file:
            links = {link.strip() for link in file.readlines() if link.strip()}
            print(f"Links carregados do arquivo: {links}")
            return links
    else:
        print("Arquivo 'seen_links.txt' não encontrado ou vazio. Criando novo arquivo.")
        return set()


# Função para salvar os links no arquivo sem interferência de cache
def save_seen_links(seen_links):
    if seen_links:
        # Filtrar apenas os links válidos que contêm números
        valid_links = [link for link in seen_links if '=' in link and link.split('=')[-1].isdigit()]
        sorted_links = sorted(
            valid_links,
            key=lambda x: int(x.split('=')[-1]),
            reverse=True
        )
        try:
            with open(SEEN_LINKS_FILE, "w") as file:
                for link in sorted_links:
                    file.write(f"{link}\n")
                print(f"Links salvos no arquivo: {sorted_links}")
        except Exception as e:
            print(f"Erro ao salvar links no arquivo: {e}")
    else:
        print("Nenhum link para salvar.")


# Função para enviar uma notificação por e-mail
def send_email_notification(article_content):
    subject = "Nova notícia detectada!"

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


# Corrigir URLs inválidas no conteúdo
def get_article_content(url):
    try:
        if not url.startswith("http"):
            url = f"https://www.pgdporto.pt/{url}"
        
        response = requests.get(url, verify=False)
        if response.status_code != 200:
            print(f"Erro ao acessar a notícia: {response.status_code}")
            return "Erro ao acessar a notícia."

        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all("p")
        return " ".join([p.get_text() for p in paragraphs])
    except Exception as e:
        print(f"Erro ao processar a notícia: {e}")
        return "Erro ao processar a notícia."
