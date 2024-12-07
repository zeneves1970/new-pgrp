import os
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URL da página a ser monitorada
BASE_URL = "https://www.pgdporto.pt/proc-web/"
URL = f"{BASE_URL}"  # Página principal
SEEN_LINKS_FILE = "seen_links.txt"  # Nome do arquivo para armazenar links já vistos

# Função para carregar links já vistos de um arquivo
def load_seen_links():
    if os.path.exists(SEEN_LINKS_FILE) and os.path.getsize(SEEN_LINKS_FILE) > 0:
        with open(SEEN_LINKS_FILE, "r") as file:
            links = {link.strip() for link in file.readlines() if link.strip()}
            print(f"Links carregados do arquivo: {links}")  # Log para verificar os links carregados
            return links
    else:
        print("Arquivo 'seen_links.txt' não encontrado ou vazio. Criando novo arquivo.")
        # Se o arquivo estiver vazio ou não existir, retorna um conjunto vazio
        return set()

# Função para salvar os links vistos em um arquivo
def save_seen_links(seen_links):
    if seen_links:
        # Ordenar os links por número em ordem decrescente
        sorted_links = sorted(
            seen_links,
            key=lambda x: int(x.split('=')[-1]),  # Obtém o número após "newsItemId="
            reverse=True  # Ordem decrescente
        )
        with open(SEEN_LINKS_FILE, "w") as file:
            for link in sorted_links:
                file.write(f"{link}\n")
            print(f"Links salvos no arquivo: {sorted_links}")  # Log para verificar o que foi salvo
    else:
        print("Nenhum link para salvar.")  # Garantindo que se não houver links, nada seja salvo


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

    # Identifica novos links
    new_links = [link for link in current_links if link not in seen_links]
    if new_links:
        # Ordenar os novos links por ordem decrescente de número
        new_links = sorted(
            new_links,
            key=lambda x: int(x.split('=')[-1]),
            reverse=True
        )
        # Envia email apenas para os novos links detectados
        for new_link in new_links:
            print(f"Nova notícia detectada: {new_link}")
            article_content = get_article_content(new_link)  # Obtém o conteúdo da notícia
            send_email_notification(article_content)  # Envia notificação por e-mail

        # Atualiza a lista de links vistos
        seen_links.update(new_links)  # Atualiza os links vistos
        save_seen_links(seen_links)  # Salva os links no arquivo
    else:
        print("Nenhuma nova notícia encontrada.")


# Execução principal
if __name__ == "__main__":
    monitor_news()
