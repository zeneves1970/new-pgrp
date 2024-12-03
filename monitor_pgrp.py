import requests
from bs4 import BeautifulSoup
import smtplib
import os
import urllib3

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal
SEEN_LINKS_FILE = "seen_links.txt"  # Nome do arquivo para armazenar links já vistos

# Função para carregar links já vistos de um arquivo
def load_seen_links():
    print("Carregando links já vistos...")
    if os.path.exists(SEEN_LINKS_FILE):
        with open(SEEN_LINKS_FILE, "r") as file:
            seen_links = set(link.strip() for link in file.readlines())
            print(f"Links carregados: {seen_links}")
            return seen_links
    print("Nenhum link visto anteriormente.")
    return set()

# Função para salvar os links vistos em um arquivo
def save_seen_links(seen_links):
    print(f"Salvando links vistos: {seen_links}")
    with open(SEEN_LINKS_FILE, "w") as file:
        file.writelines(f"{link}\n" for link in seen_links)

# Função para obter os links das notícias
def get_news_links(url):
    print(f"Acessando a página principal: {url}")
    try:
        response = requests.get(url, verify=False, timeout=10)  # Timeout de 10 segundos
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        news_section = soup.find_all('div', class_='box-news-home-body-more')
        if not news_section:
            print("Nenhuma seção de notícias encontrada.")
            return []
        links = [BASE_URL + item.find('a')['href'] for item in news_section if item.find('a')]
        print(f"Links encontrados: {links}")
        return links
    except Exception as e:
        print(f"Erro ao acessar a página principal: {e}")
        return []

# Função para obter o conteúdo da página de notícia
def get_article_content(link):
    print(f"Acessando conteúdo da notícia: {link}")
    try:
        response = requests.get(link, verify=False, timeout=10)  # Timeout de 10 segundos
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        body = soup.find('div', class_='news-detail')  # Procurando a div com a classe 'news-detail'
        content = body.text.strip() if body else "Conteúdo não encontrado"
        print(f"Conteúdo obtido: {content[:100]}...")  # Exibe os primeiros 100 caracteres para depuração
        return content
    except Exception as e:
        print(f"Erro ao acessar o conteúdo da notícia: {e}")
        return "Erro ao obter conteúdo da notícia."

# Função para enviar uma notificação por e-mail
def send_email_notification(article_content):
    from_email = os.getenv("EMAIL_USER")  # Acessando o secret EMAIL_USER
    from_password = os.getenv("EMAIL_PASSWORD")  # Acessando o secret EMAIL_PASSWORD
    to_email = "jneves@lusa.pt"  # Destinatário
    subject = "Nova notícia detectada!"

    email_text = f"""From: {from_email}
To: {to_email}
Subject: {subject}

{article_content}
"""
    try:
        print(f"Enviando e-mail para {to_email}...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            server.sendmail(from_email, to_email, email_text.encode("utf-8"))
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# Função principal para monitorar mudanças
def monitor_news():
    try:
        print("Iniciando monitoramento...")
        seen_links = load_seen_links()  # Carrega links já vistos do arquivo
        current_links = get_news_links(URL)  # Obtém os links atuais

        if not current_links:
            print("Nenhum link encontrado na página.")
            return

        new_links = set(current_links) - seen_links  # Identifica novos links
        print(f"Novos links detectados: {new_links}")

        if new_links:
            for link in new_links:
                print(f"Processando nova notícia: {link}")
                article_content = get_article_content(link)
                send_email_notification(article_content)
            seen_links.update(new_links)
            save_seen_links(seen_links)
        else:
            print("Nenhuma nova notícia encontrada.")
    except Exception as e:
        print(f"Erro inesperado durante o monitoramento: {e}")

if __name__ == "__main__":
    monitor_news()
