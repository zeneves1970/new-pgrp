import os
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3
import time

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
SEEN_LINKS_FILE = "seen_links.txt"  # Nome do arquivo para armazenar links já vistos

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

response = requests.get(url, headers=headers, verify=False)

# Função para carregar links já vistos de um arquivo
def load_seen_links():
    if os.path.exists(SEEN_LINKS_FILE) and os.path.getsize(SEEN_LINKS_FILE) > 0:
        try:
            with open(SEEN_LINKS_FILE, "r") as file:
                links = {link.strip() for link in file.readlines() if link.strip()}
                print(f"Links carregados da cache: {links}")
                return links
        except Exception as e:
            print(f"Erro ao carregar cache: {e}")
    else:
        print("Cache vazio ou não existe. Criando novo conjunto de links.")
    return set()


def save_seen_links(seen_links):
    try:
        with open(SEEN_LINKS_FILE, "w") as file:
            for link in seen_links:
                file.write(f"{link}\n")
            file.flush()
            os.fsync(file.fileno())  # Garante que as mudanças sejam persistidas
        print("Cache atualizado com links novos.")
    except Exception as e:
        print(f"Erro ao salvar links na cache: {e}")



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


def get_news_links(url):
    retries = 3  # Tentativas de conexão
    for attempt in range(retries):
        try:
            response = requests.get(url, verify=False, timeout=10)  # timeout de 10 segundos
            if response.status_code == 200:
                break  # Se a conexão for bem-sucedida, sai do loop
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:  # Tentar novamente se não for a última tentativa
                print(f"Tentativa {attempt + 1} falhou, tentando novamente...")
                time.sleep(5)  # Esperar 5 segundos antes de tentar novamente
            else:
                print(f"Erro ao acessar a página após {retries} tentativas: {e}")
                return []  # Retorna lista vazia se todas as tentativas falharem
    # Parse da resposta com BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')
    links = set()
    for a_tag in soup.find_all("a", href=True):
        if "news.jsf" in a_tag['href']:
            full_link = f"https://www.pgdporto.pt/proc-web/{a_tag['href']}"
            links.add(full_link)
    return links

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
    monitor_news()
