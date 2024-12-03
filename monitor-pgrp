import requests
from bs4 import BeautifulSoup
import time
import smtplib
import urllib3
import os

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal

# Função para obter os links das notícias
def get_news_links(url):
    response = requests.get(url, verify=False)  # Ignorando verificação SSL
    soup = BeautifulSoup(response.text, 'html.parser')
    # Localizar a seção de notícias
    news_section = soup.find_all('div', class_='box-news-home-body-more')
    if not news_section:
        return []
    # Extrair links das notícias
    links = [BASE_URL + item.find('a')['href'] for item in news_section if item.find('a')]
    return links

# Função para obter o conteúdo da página de notícia
def get_article_content(link):
    response = requests.get(link, verify=False)  # Ignorando verificação SSL
    soup = BeautifulSoup(response.text, 'html.parser')

    # Procurar pela div que contém o conteúdo da notícia
    body = soup.find('div', class_='news-detail')  # Procurando a div com a classe 'news-detail'

    # Se o conteúdo não for encontrado, podemos retornar um aviso padrão
    body_text = body.text.strip() if body else "Conteúdo não encontrado"

    return body_text

# Função para enviar uma notificação por e-mail
def send_email_notification(article_content):
    from_email = os.getenv("EMAIL_USER")  # Acessando o secret EMAIL_USER
    from_password = os.getenv("EMAIL_PASSWORD")  # Acessando o secret EMAIL_PASSWORD
    to_email = "jneves@lusa.pt"  # Destinatário
    subject = "Nova notícia detectada!"
    
    # Criação do corpo do e-mail
    email_text = f"""From: {from_email}
To: {to_email}
Subject: {subject}

{article_content}
"""
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            # Enviar o e-mail com conteúdo da notícia
            server.sendmail(from_email, to_email, email_text.encode("utf-8"))
    except Exception as e:
        print("Erro ao enviar e-mail:", e)

# Função para salvar os links processados
def save_seen_links(links):
    with open("seen_links.txt", "w") as file:
        for link in links:
            file.write(f"{link}\n")

# Função para carregar os links processados
def load_seen_links():
    try:
        with open("seen_links.txt", "r") as file:
            return set(line.strip() for line in file)
    except FileNotFoundError:
        return set()

# Função principal para monitorar mudanças
def monitor_news():
    # Carregar os links vistos
    seen_links = load_seen_links()
    
    # Coletar os links iniciais
    links = get_news_links(URL)
    if not links:
        return  # Interrompe a execução se não houver links iniciais

    # Verifica se há novos links desde a última execução
    new_links = set(links) - seen_links

    if new_links:
        for link in new_links:
            article_content = get_article_content(link)
            send_email_notification(article_content)
        seen_links.update(new_links)
        save_seen_links(seen_links)  # Salva os links vistos

    # Continuar monitoramento periódico
    while True:
        time.sleep(900)  # Espera 15 minutos (900 segundos)
        
        # Recupera os links da página novamente
        current_links = get_news_links(URL)
        if not current_links:
            continue  # Ignora esta iteração caso não consiga recuperar links

        # Verifica se há novos links
        new_links = set(current_links) - seen_links
        
        if new_links:
            for link in new_links:
                article_content = get_article_content(link)
                send_email_notification(article_content)
            seen_links.update(new_links)
            save_seen_links(seen_links)  # Salva os links vistos

if __name__ == "__main__":
    monitor_news()
