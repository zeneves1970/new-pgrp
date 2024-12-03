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
    if os.path.exists(SEEN_LINKS_FILE):
        with open(SEEN_LINKS_FILE, "r") as file:
            return set(link.strip() for link in file.readlines())
    return set()

# Função para salvar os links vistos em um arquivo
def save_seen_links(seen_links):
    with open(SEEN_LINKS_FILE, "w") as file:
        file.writelines(f"{link}\n" for link in seen_links)

# Função para obter os links das notícias
def get_news_links(url):
    try:
        response = requests.get(url, verify=False)  # Ignorando verificação SSL
        response.raise_for_status()  # Levanta uma exceção para códigos de erro HTTP
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição para a página principal: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')

    # Encontrar as notícias dentro da <div class="box-news-home-title">
    news_section = soup.find_all('div', class_='box-news-home-title')
    
    if not news_section:
        print("Nenhuma seção de notícias encontrada.")
        return []

    # Retornar os links completos das notícias
    return [BASE_URL + item.find('a')['href'] for item in news_section if item.find('a')]

# Função para obter o conteúdo da página de notícia
def get_article_content(link):
    try:
        response = requests.get(link, verify=False)  # Ignorando verificação SSL
        response.raise_for_status()  # Levanta uma exceção para códigos de erro HTTP
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição para o link da notícia: {e}")
        return "Conteúdo não encontrado"
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Encontrar o conteúdo da notícia dentro da <div class="news-detail">
    body = soup.find('div', class_='news-detail')
    
    if not body:
        print(f"Conteúdo da notícia não encontrado para o link: {link}")
        return "Conteúdo não encontrado"
    
    return body.text.strip()

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
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            server.sendmail(from_email, to_email, email_text.encode("utf-8"))
        print(f"Email enviado com sucesso.")
    except Exception as e:
        print("Erro ao enviar e-mail:", e)

# Função principal para monitorar mudanças
def monitor_news():
    seen_links = load_seen_links()  # Carrega links já vistos do arquivo
    current_links = get_news_links(URL)  # Obtém os links atuais

    if not current_links:
        print("Nenhum link encontrado na página.")
        return

    new_links = set(current_links) - seen_links  # Identifica novos links
    if new_links:
        # Pega o primeiro novo link
        new_link = next(iter(new_links))
        print(f"Nova notícia detectada: {new_link}")
        
        # Obter o conteúdo da notícia
        article_content = get_article_content(new_link)  # Obtém o conteúdo da notícia
        send_email_notification(article_content)  # Envia notificação por e-mail
        
        # Atualiza os links vistos
        seen_links.update(new_links)  # Atualiza os links vistos
        save_seen_links(seen_links)  # Salva os links vistos no arquivo
    else:
        print("Nenhuma nova notícia encontrada.")

if __name__ == "__main__":
    monitor_news()
