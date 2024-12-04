import requests
from bs4 import BeautifulSoup
import smtplib
import os
import urllib3
from time import sleep

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal
SEEN_LINKS_FILE = "seen_links.txt"  # Nome do arquivo para armazenar links já vistos

# Cabeçalho User-Agent para evitar bloqueios
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

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

# Função para obter os links das notícias com re-tentativas
def get_news_links(url, retries=5):
    for attempt in range(retries):
        try:
            print(f"Tentando acessar a página: {url} (Tentativa {attempt + 1})")
            response = requests.get(url, headers=HEADERS, verify=False)  # Ignorando verificação SSL
            response.raise_for_status()  # Levanta uma exceção para códigos de erro HTTP
            print("Página acessada com sucesso!")
            soup = BeautifulSoup(response.text, 'html.parser')

            # Encontrar as notícias dentro da <div class="box-news-home-title">
            news_section = soup.find_all('div', class_='box-news-home-title')
            if not news_section:
                print("Nenhuma seção de notícias encontrada.")
                return []
            return [BASE_URL + item.find('a')['href'] for item in news_section if item.find('a')]
        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição para a página principal: {e}")
            if attempt < retries - 1:
                print("Tentando novamente...")
                sleep(10)  # Espera 10 segundos antes de tentar novamente
            else:
                print("Máximo de tentativas atingido")
                return []
    return []

# Função para obter o conteúdo da página de notícia com re-tentativas
def get_article_content(link, retries=5):
    for attempt in range(retries):
        try:
            print(f"Tentando acessar o conteúdo da notícia: {link} (Tentativa {attempt + 1})")
            response = requests.get(link, headers=HEADERS, verify=False)  # Ignorando verificação SSL
            response.raise_for_status()  # Levanta uma exceção para códigos de erro HTTP
            print(f"Conteúdo da notícia acessado com sucesso: {link}")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar o conteúdo da notícia dentro da <div class="news-detail">
            body = soup.find('div', class_='news-detail')
            if not body:
                print(f"Conteúdo da notícia não encontrado para o link: {link}")
                return "Conteúdo não encontrado"
            return body.text.strip()
        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição para o link da notícia: {e}")
            if attempt < retries - 1:
                print("Tentando novamente...")
                sleep(10)  # Espera 10 segundos antes de tentar novamente
            else:
                print("Máximo de tentativas atingido")
                return "Conteúdo não encontrado"
    return "Conteúdo não encontrado"

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
    print(f"Links já vistos: {seen_links}")
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
