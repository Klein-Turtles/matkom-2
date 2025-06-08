import os
import re
import sys
import requests # Masih diperlukan untuk beberapa kasus atau jika ingin fallbacks
from bs4 import BeautifulSoup
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
from db_manager import DBManager # Hanya dibutuhkan jika ingin test standalone

def crawl_website(start_url, base_domain, max_pages_to_crawl=100):
    """
    Melakukan crawling pada situs web menggunakan Selenium, mengekstrak konten dan tautan.
    Mampu menangani situs dengan konten yang dimuat JavaScript dan lebih cerdas dalam ekstraksi konten.
    """
    pages_data = []
    visited_urls = set()
    urls_to_visit = deque([start_url])

    # Konfigurasi WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Menjalankan browser tanpa UI
    options.add_argument('--no-sandbox') # Diperlukan untuk lingkungan tertentu
    options.add_argument('--disable-dev-shm-usage') # Diperlukan untuk lingkungan tertentu
    options.add_argument('--disable-gpu') # Mencegah isu rendering di headless mode
    options.add_argument('--log-level=3') # Menekan pesan log yang tidak perlu dari Chrome

    # Inisialisasi driver Chrome
    try:
        # Jika chromedriver.exe ada di PATH sistem, atau di direktori proyek yang bisa diakses:
        driver = webdriver.Chrome(options=options)
        # Jika Anda perlu menentukan jalur eksplisit ke chromedriver.exe:
        # service = Service(executable_path='C:/path/to/your/chromedriver.exe')
        # driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException as e:
        print(f"Error: Gagal menginisialisasi ChromeDriver. Pastikan chromedriver.exe ada di PATH atau jalurnya benar. Detail: {e}")
        return []

    print(f"Memulai crawling dari: {start_url}")
    print(f"Membatasi crawling pada domain: {base_domain}")

    try:
        while urls_to_visit and len(visited_urls) < max_pages_to_crawl:
            current_url = urls_to_visit.popleft()

            # Pastikan URL belum dikunjungi dan tidak ada fragmen (#)
            parsed_current_url = urlparse(current_url)
            clean_current_url = urljoin(current_url, parsed_current_url.path) # Hapus fragmen dan query params
            
            if clean_current_url in visited_urls:
                continue

            print(f"  - Mengambil: {current_url}")
            visited_urls.add(clean_current_url) # Simpan URL bersih ke daftar yang sudah dikunjungi

            try:
                driver.get(current_url)
                
                # Tambahkan waktu tunggu eksplisit untuk elemen body agar halaman dimuat
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Ekstrak Judul
                title = soup.find('title').get_text(strip=True) if soup.find('title') else 'Tidak Ada Judul'

                # --- Bagian Ekstraksi Konten Cerdas ---
                main_content_area = None
                # Prioritas 1: Cari elemen-elemen yang biasa berisi konten artikel/postingan
                for selector in ['main', 'article', 'div[class*="entry-content"]', 'div[class*="post-content"]', 
                                 'div[id="main-content"]', 'div[id="content"]', 'div[id="primary"]', 
                                 'div[class*="content-area"]', 'div[class*="site-main"]']:
                    main_content_area = soup.select_one(selector)
                    if main_content_area:
                        break

                if main_content_area:
                    # Jika area konten spesifik ditemukan, hapus elemen navigasi/boilerplate di dalamnya
                    # Ini berguna jika ada menu di dalam area konten utama
                    for unwanted_tag in main_content_area.find_all(['nav', 'aside', 'ul'], class_=re.compile(r'(menu|nav|sidebar|widgets)')):
                        unwanted_tag.decompose() # Hapus dari pohon parsing
                    
                    # Ekstrak teks dari tag-tag umum di dalam area konten yang ditemukan
                    content_tags = main_content_area.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li', 'span', 'a'])
                    main_content_text = ' '.join([tag.get_text(separator=' ', strip=True) for tag in content_tags])
                else:
                    # Fallback: Jika tidak ada area konten spesifik, coba hapus elemen boilerplate dari seluruh body
                    for unwanted_tag in soup.find_all(['header', 'footer', 'nav', 'aside', 'form'], class_=re.compile(r'(menu|nav|sidebar|header|footer|search)')):
                        unwanted_tag.decompose() # Hapus dari seluruh soup
                    
                    # Lalu ambil teks dari tag-tag umum yang tersisa di body
                    content_tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li', 'span', 'a'])
                    main_content_text = ' '.join([tag.get_text(separator=' ', strip=True) for tag in content_tags])
                
                # --- Pembersihan Teks Lanjutan ---
                # Hapus spasi berlebihan
                main_content_text = re.sub(r'\s+', ' ', main_content_text).strip()
                
                # Filter duplikasi baris/frasa yang sering muncul dari menu/linklist yang terlewat
                # Ini adalah heuristik, mungkin perlu disesuaikan jika terlalu agresif/pasif
                clean_text_parts = []
                seen_phrases = set()
                # Memecah teks menjadi "kalimat" atau bagian berdasarkan titik atau ukuran blok
                # Untuk kesederhanaan, mari kita pecah berdasarkan 20 kata dan cek duplikasi
                words_in_content = main_content_text.split()
                chunk_size = 20 # Ukuran chunk untuk mendeteksi duplikasi
                for i in range(0, len(words_in_content), chunk_size):
                    chunk = " ".join(words_in_content[i:i+chunk_size])
                    if chunk not in seen_phrases:
                        clean_text_parts.append(chunk)
                        seen_phrases.add(chunk)
                main_content_text = " ".join(clean_text_parts).strip()


                # Gabungkan judul dan konten
                full_content = f"{title}\n\n{main_content_text}"

                # Ekstrak Tautan Keluar (Link ke)
                links_to = []
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    absolute_url = urljoin(current_url, href)
                    parsed_absolute_url = urlparse(absolute_url)

                    # Pastikan link berada dalam domain yang sama dan merupakan URL yang valid
                    # Hindari link jangkar (#), link email (mailto:), dan link ke file tertentu
                    if parsed_absolute_url.netloc == base_domain and \
                       parsed_absolute_url.scheme in ['http', 'https'] and \
                       not parsed_absolute_url.fragment and \
                       not parsed_absolute_url.query and \
                       not absolute_url.startswith('mailto:') and \
                       not absolute_url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.jpg', '.png', '.gif')) and \
                       urljoin(absolute_url, parsed_absolute_url.path) not in visited_urls: # Hindari URL yang sudah dikunjungi (versi bersih)
                        
                        clean_link_url = urljoin(absolute_url, parsed_absolute_url.path) # Bersihkan URL target juga
                        if clean_link_url != clean_current_url: # Hindari link ke halaman itu sendiri
                            links_to.append(clean_link_url)
                            urls_to_visit.append(clean_link_url) # Tambahkan URL bersih ke antrian

                pages_data.append({
                    'url': clean_current_url, # Simpan URL yang sudah bersih
                    'title': title, 
                    'content': full_content, 
                    'links_to': links_to
                })
                print(f"    - Berhasil: '{clean_current_url}' (Judul: '{title}', ditemukan {len(links_to)} link baru)")

            except TimeoutException:
                print(f"    - Timeout saat mengambil {current_url}.")
            except requests.exceptions.RequestException as e:
                print(f"    - Gagal mengambil {current_url} (HTTP/Network error): {e}")
            except Exception as e:
                print(f"    - Error memproses {current_url}: {e}")
                
        print(f"\nCrawling selesai. Total halaman yang di-crawl: {len(pages_data)}")
        return pages_data
    finally:
        if 'driver' in locals() and driver:
            driver.quit()
            print("WebDriver ditutup.")

def populate_database(pages_data, db_manager):
    """
    Mengisi database dengan data halaman dan link yang sudah di-crawl.
    Dilakukan dalam dua pass:
    1. Masukkan semua halaman untuk mendapatkan ID.
    2. Masukkan semua link menggunakan ID yang sudah ada.
    """
    url_to_id_map = {}

    print("\n--- Memasukkan Halaman ke Database (Pass 1) ---")
    for page in pages_data:
        # Asumsi insert_page(url, content)
        page_id = db_manager.insert_page(page['url'], page['content']) 
        if page_id is not None:
            url_to_id_map[page['url']] = page_id
        else:
            print(f"Warning: Gagal memasukkan halaman '{page['url']}' ke database (mungkin duplikat atau error DB).")

    print("\n--- Memasukkan Link ke Database (Pass 2) ---")
    for page in pages_data:
        source_url = page['url']
        source_id = url_to_id_map.get(source_url) 

        if source_id is None:
            print(f"Warning: ID tidak ditemukan untuk URL sumber: {source_url}. Lewati link-nya.")
            continue

        for target_url in page['links_to']:
            target_id = url_to_id_map.get(target_url) 

            if target_id is None:
                print(f"Warning: ID tidak ditemukan untuk URL target: {target_url} (dari {source_url}). Link diabaikan.")
                continue 

            db_manager.insert_link(source_id, target_id)

    print("\nProses pengisian database selesai.")

# Blok __main__ ini untuk menjalankan crawler secara standalone
if __name__ == '__main__':
    start_url = "https://elektro.um.ac.id/"
    parsed_start_url = urlparse(start_url)
    base_domain = parsed_start_url.netloc

    db_manager = DBManager()
    db_manager.connect()
    
    if db_manager.connection:
        db_manager.create_tables() 
        db_manager.clear_tables() # Disarankan untuk membersihkan DB sebelum crawl baru
        
        pages_data = crawl_website(start_url, base_domain, max_pages_to_crawl=50) # Batasi 50 halaman untuk uji coba
        populate_database(pages_data, db_manager)
        db_manager.close_connection()
    else:
        print("Tidak dapat melakukan crawling karena koneksi database gagal.")
