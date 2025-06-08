import os
import re
import sys
from urllib.parse import urljoin, urlparse
from collections import deque
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Tambahkan path ke folder database agar db_manager bisa diimpor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
from db_manager import DBManager  # Hanya dibutuhkan jika ingin test standalone

def crawl_website(start_url, base_domain, max_pages_to_crawl=100):
    pages_data = []
    visited_urls = set()
    urls_to_visit = deque([start_url])

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print(f"Error: {e}")
        return []

    try:
        while urls_to_visit and len(visited_urls) < max_pages_to_crawl:
            current_url = urls_to_visit.popleft()
            parsed = urlparse(current_url)
            clean_url = urljoin(current_url, parsed.path)

            if clean_url in visited_urls:
                continue

            visited_urls.add(clean_url)
            print(f"Crawling: {clean_url}")

            try:
                driver.get(current_url)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                title = driver.title.strip() if driver.title else 'Tidak Ada Judul'

                # Cari area konten utama
                content = ""
                found = False
                for selector in [
                    "main", "article", "div[class*='entry-content']", "div[class*='post-content']",
                    "div[id='main-content']", "div[id='content']", "div[id='primary']",
                    "div[class*='content-area']", "div[class*='site-main']"]:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        content = element.text
                        found = True
                        break
                    except:
                        continue
                if not found:
                    body = driver.find_element(By.TAG_NAME, "body")
                    content = body.text

                # Pembersihan teks sederhana
                content = re.sub(r'\s+', ' ', content).strip()

                full_content = f"{title}\n\n{content}"

                # Ekstrak link unik
                links_to = set()
                a_tags = driver.find_elements(By.TAG_NAME, "a")
                for a in a_tags:
                    href = a.get_attribute("href")
                    if href:
                        href_parsed = urlparse(href)
                        cleaned_href = urljoin(href, href_parsed.path)

                        if (href_parsed.netloc == base_domain and
                            href_parsed.scheme in ["http", "https"] and
                            not href_parsed.fragment and
                            not href_parsed.query and
                            not cleaned_href.lower().endswith((
                                ".pdf", ".doc", ".docx", ".xls", ".xlsx",
                                ".zip", ".rar", ".jpg", ".png", ".gif")) and
                            cleaned_href != clean_url and
                            cleaned_href not in visited_urls and
                            cleaned_href not in urls_to_visit and
                            cleaned_href not in links_to):
                            links_to.add(cleaned_href)
                            urls_to_visit.append(cleaned_href)

                pages_data.append({
                    "url": clean_url,
                    "title": title,
                    "content": full_content,
                    "links_to": list(links_to)
                })

                print(f"  -> Done: {title} ({len(links_to)} links found)")

            except TimeoutException:
                print(f"  !! Timeout on: {current_url}")
            except Exception as e:
                print(f"  !! Error on {current_url}: {e}")

        return pages_data

    finally:
        driver.quit()
        print("WebDriver closed.")

def populate_database(pages_data, db_manager):
    url_to_id = {}

    print("\nInserting pages into database...")
    for page in pages_data:
        page_id = db_manager.insert_page(page['url'], page['content'])
        if page_id:
            url_to_id[page['url']] = page_id

    print("\nInserting links into database...")
    for page in pages_data:
        source_id = url_to_id.get(page['url'])
        if not source_id:
            continue

        for link in page['links_to']:
            target_id = url_to_id.get(link)
            if target_id:
                db_manager.insert_link(source_id, target_id)

if __name__ == '__main__':
    start_url = "https://elektro.um.ac.id/"
    parsed = urlparse(start_url)
    base_domain = parsed.netloc

    db_manager = DBManager()
    db_manager.connect()

    if db_manager.connection:
        db_manager.create_tables()
        db_manager.clear_tables()

        data = crawl_website(start_url, base_domain, max_pages_to_crawl=50)
        populate_database(data, db_manager)

        db_manager.close_connection()
    else:
        print("Database connection failed.")
