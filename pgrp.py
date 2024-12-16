import os
import requests
from bs4 import BeautifulSoup
import smtplib
import urllib3

# Suprime avisos sobre SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurações do e-mail
EMAIL_USER = "EMAIL_USER"  # Substitua pelo seu e-mail
EMAIL_PASSWORD = "EMAIL_PASSWORD"  # Substitua pela sua senha ou App Password
TO_EMAIL = "TO_EMAIL"  # Substitua pelo e-mail do destinatário

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
        # Ordenar os links pela numeração no final (como no exemplo original)
        sorted_links = sorted(
            seen_links,
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
        body = " ".join(
            [elem.get_text(strip=True) for elem in body_elem.find_all(["p", "div"], recursive=True)]
        ) if body_elem else "Conteúdo não encontrado."

        # Montar o conteúdo final do e-mail
        article_content = f"""
        {title}\n
        {summary}\n
        {body}
        """

        if not body.strip():
            print(f"Conteúdo vazio após extração na URL: {url}")
            return "Conteúdo vazio."

        return article_content
    except Exception as e:
        print(f"Erro ao processar a notícia: {e}")
        return "Erro ao processar a notícia."


# Função principal para monitorar mudanças
 seen_links = load_seen_links()
    current_links = get_news_links(URL)

    if not current_links:
        print("Nenhum link encontrado na página.")
        return

    new_links = {link for link in current_links if link not in seen_links}

    if new_links:
        print(f"Novos links encontrados: {new_links}")
        for new_link in new_links:
            print(f"Detectando nova notícia: {new_link}")
            try:
                send_email_notification(get_article_content(new_link))
            except Exception as e:
                print(f"Erro ao enviar email: {e}")

        # Salvar no cache imediatamente após detectar e processar novos dados.
        seen_links.update(new_links)
        save_seen_links(seen_links)
    else:
        print("Nenhuma nova notícia encontrada.")


# Execução principal
if __name__ == "__main__":
    monitor_news()

