from flask import Flask, render_template, request, g # Import 'g' untuk manajemen koneksi
import os
import sys
import traceback
import re
import difflib # Diperlukan untuk perbaikan typo

# Tambahkan path ke folder src agar modul-modul di dalamnya bisa diimpor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'utils')))


from db_manager import DBManager # Import DBManager yang sudah kita buat

# Konfigurasi Flask agar tahu di mana mencari template dan file statis
app = Flask(__name__,
            template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'templates')),
            static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static')))

# Stopwords dasar Bahasa Indonesia (bisa kamu tambahkan)
stopwords = {
    "yang", "dan", "di", "ke", "untuk", "dengan", "adalah", "pada",
    "dari", "sebagai", "oleh", "dalam", "itu", "ini", "atau", "sudah",
    "akan", "karena", "juga", "bahwa", "oleh", "maka", "dapat", "lebih",
    "saya", "kami", "mereka", "dia", "anda", "kita", "nya", "hal", "pun",
    "begitu", "saja", "masih", "tapi", "tetapi", "tidak", "belum", "serta",
    "guna", "bagi", "setiap", "seluruh", "semua", "lain", "bahkan"
}

# Variabel global untuk IDF tidak lagi dibutuhkan, jadi dihapus
# document_frequencies = {}
# idf_scores = {}
# total_documents = 0

# Fungsi untuk mendapatkan instance DBManager yang terhubung
def get_db():
    """
    Mengembalikan instance DBManager yang terhubung untuk permintaan saat ini.
    Jika belum ada, akan membuat dan menyimpannya di g.
    """
    if 'db_manager' not in g:
        g.db_manager = DBManager()
        g.db_manager.connect()
        if not g.db_manager.connection:
            # Ini akan menyebabkan error yang bisa ditangkap oleh @app.teardown_request
            raise ConnectionError("Gagal terhubung ke database.")
    return g.db_manager

# Fungsi untuk menutup koneksi database setelah setiap permintaan
@app.teardown_appcontext
def close_db(e=None):
    """
    Menutup koneksi database di akhir setiap permintaan.
    """
    db_manager = g.pop('db_manager', None)
    if db_manager is not None and db_manager.connection:
        db_manager.close_connection()

# @app.before_request calculate_idf_on_startup dihapus karena tidak ada IDF
# def calculate_idf_on_startup():
#     ... (logika IDF dihapus) ...

@app.route('/')
def index():
    """
    Rute untuk halaman utama (form pencarian).
    """
    return render_template('index.html')

# Fungsi untuk mendaftarkan filter 'highlight' di Jinja2
@app.template_filter()
def highlight(text, query):
    """
    Fungsi untuk menyorot kata-kata yang cocok dalam teks.
    """
    words_to_highlight = re.findall(r'\w+', query.lower())
    for word in words_to_highlight:
        # Gunakan word boundary (\b) untuk mencocokkan kata utuh saja
        # Gunakan re.escape untuk menangani karakter khusus dalam kata kunci
        text = re.sub(r'\b(' + re.escape(word) + r')\b', r'<mark>\1</mark>', text, flags=re.IGNORECASE)
    return text

# Fungsi baru untuk menghitung skor relevansi sederhana dengan boost judul
def calculate_simple_relevance_score(doc, query_words_filtered, original_query_text):
    """
    Menghitung skor relevansi sederhana untuk dokumen berdasarkan kata-kata query yang difilter.
    Memberikan boost signifikan untuk kecocokan judul dan mempertimbangkan frekuensi kata.
    """
    # Ekstrak judul dari konten (asumsi judul adalah baris pertama)
    doc_content_lines = doc['content'].split('\n', 1)
    doc_title_extracted = doc_content_lines[0].strip() if doc_content_lines else ''
    main_doc_content = doc_content_lines[1].strip() if len(doc_content_lines) > 1 else doc['content'].strip() # Gunakan full content jika tidak ada baris kedua

    score = 0
    
    # Hitung frekuensi kata kunci di konten utama
    # Menggunakan query_words_filtered (sudah difilter stopwords)
    for word in query_words_filtered:
        score += main_doc_content.lower().count(word)

    # Berikan bobot lebih tinggi untuk kata kunci yang ada di judul
    for word in query_words_filtered:
        score += doc_title_extracted.lower().count(word) * 10 # Bobot 10x untuk judul

    # BERIKAN BOOST SANGAT TINGGI UNTUK KECOCOKAN JUDUL EKSPLISIT DENGAN QUERY ASLI
    if original_query_text.lower() == doc_title_extracted.lower():
        score += 100000000 # Boost sangat tinggi
    elif original_query_text.lower() in doc_title_extracted.lower() and len(original_query_text) > 3:
        score += 10000000 # Boost tinggi jika substring judul
    
    # Boost jika query ada di URL
    if original_query_text.lower() in doc['url'].lower():
        score += 1000000

    return score


@app.route('/search', methods=['GET'])
def search():
    """
    Rute untuk memproses permintaan pencarian.
    Mengambil kata kunci dari query parameter 'q', melakukan pencarian,
    dan menampilkan hasilnya.
    """
    query = request.args.get('q', '').strip()
    results = []
    
    try:
        db_manager = get_db() 
        if query:
            all_raw_docs = db_manager.get_all_documents() # Ambil semua dokumen untuk pemrosesan
            
            # Preprocessing query: tokenisasi dan filter stopwords
            query_words = re.findall(r'\w+', query)
            filtered_query_words = [word for word in query_words if word not in stopwords]

            # Mengambil semua kata dari semua dokumen untuk koreksi typo
            all_words_for_typo = set()
            for doc in all_raw_docs:
                text_to_tokenize = f"{doc.get('judul', '')} {doc.get('content', '')}".lower() # Asumsi judul ada di sini
                words = re.findall(r'\w+', text_to_tokenize)
                filtered_words = [word for word in words if word not in stopwords]
                all_words_for_typo.update(filtered_words)

            # Koreksi typo untuk kata kunci pencarian
            corrected_words = []
            for word in filtered_query_words:
                match = []
                if word: 
                    match = difflib.get_close_matches(word, list(all_words_for_typo), n=1, cutoff=0.7)
                corrected_words.append(match[0] if match else word)

            # Filter dokumen yang relevan berdasarkan pola pencarian yang sudah dikoreksi
            patterns = [re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE) for word in corrected_words]
            filtered_docs = []
            for doc in all_raw_docs: 
                text_to_search = f"{doc.get('judul', '')} {doc.get('content', '')}" # Asumsi judul ada di sini
                if any(p.search(text_to_search) for p in patterns):
                    filtered_docs.append(doc)
            
            # Jika tidak ada dokumen yang relevan, hasilnya kosong
            if not filtered_docs:
                return render_template('results.html', results=[], query=query, corrected=None)

            # PageRank scores (ambil dari database)
            pagerank_scores = {doc['id']: doc['pagerank_score'] for doc in all_raw_docs}

            # Skoring relevansi berdasarkan keyword (menggunakan simple relevance score)
            simple_relevance_scores = {doc['id']: calculate_simple_relevance_score(doc, filtered_query_words, query) for doc in filtered_docs}

            # Normalisasi skor relevansi sederhana
            max_simple_relevance_score = max(simple_relevance_scores.values(), default=0)
            if max_simple_relevance_score == 0:
                normalized_simple_relevance_scores = {doc_id: 0.0 for doc_id in simple_relevance_scores.keys()}
            else:
                normalized_simple_relevance_scores = {
                    doc_id: score / max_simple_relevance_score for doc_id, score in simple_relevance_scores.items()
                }

            # Gabungkan dengan PageRank
            # Alpha sangat kecil agar relevansi keyword sederhana dominan
            alpha = 0.0001 # Misalnya, 0.01% PageRank, 99.99% relevansi sederhana
            
            combined_scores = {}
            for doc in filtered_docs:
                doc_id = doc['id']
                pr_score = pagerank_scores.get(doc_id, 0.0) 
                simple_kw_score = normalized_simple_relevance_scores.get(doc_id, 0.0) 

                combined_scores[doc_id] = (alpha * pr_score) + ((1 - alpha) * simple_kw_score)
                # Tambahkan skor gabungan ke objek dokumen agar bisa diakses di template
                doc['final_score'] = combined_scores[doc_id]

            # Debugging untuk melihat skor
            print("\n--- DEBUG SCORES ---")
            for doc in filtered_docs:
                doc_id = doc['id']
                # Asumsi judul ada di baris pertama konten
                title_for_debug = doc['content'].split('\n', 1)[0].strip() if doc['content'] else 'No Title'
                print(f"Doc ID {doc_id}, Title: '{title_for_debug}'")
                print(f"  Keyword Score (Simple, norm): {normalized_simple_relevance_scores.get(doc_id, 0):.4f}")
                print(f"  PageRank Score: {pagerank_scores.get(doc_id, 0):.4f}")
                print(f"  Combined Score: {combined_scores.get(doc_id, 0):.4f}")
            print("--- END DEBUG ---")


            # Urutkan berdasarkan skor akhir
            sorted_docs = sorted(
                filtered_docs,
                key=lambda doc: doc.get('final_score', 0), # Urutkan berdasarkan final_score
                reverse=True
            )
            results = sorted_docs

        else:
            print("Pencarian kosong.")
            # corrected akan tetap None jika query kosong
            corrected_words = [] # Inisialisasi agar tidak error jika query kosong
    except ConnectionError as e:
        print(f"ERROR KONEKSI DATABASE DI /search: {e}")
        traceback.print_exc()
        return "Error: Tidak dapat terhubung ke database untuk pencarian.", 500
    except Exception as e:
        print(f"TERJADI ERROR UMUM DI /search: {e}")
        traceback.print_exc()
        return "Terjadi kesalahan server.", 500
    
    return render_template(
        'results.html', 
        query=query, 
        results=results, 
        corrected=' '.join(corrected_words) if corrected_words != filtered_query_words else None
    )

@app.route('/view_page/<int:page_id>')
def view_page_content(page_id):
    page_data = None
    try:
        db_manager = get_db()
        page_data = db_manager.get_document_by_id(page_id)
    except ConnectionError as e:
        print(f"ERROR KONEKSI DATABASE DI /view_page/{page_id}: {e}")
        traceback.print_exc()
        return "Error: Tidak dapat terhubung ke database untuk menampilkan halaman.", 500
    except Exception as e:
        print(f"TERJADI ERROR UMUM DI /view_page/{page_id}: {e}")
        traceback.print_exc()
        return "Terjadi kesalahan server.", 500

    if page_data:
        full_content_from_db = page_data.get('content', '')
        content_lines = full_content_from_db.split('\n', 1)
        
        display_title = content_lines[0].strip() if content_lines else 'Tidak Ada Judul'
        display_content = content_lines[1].strip() if len(content_lines) > 1 else full_content_from_db.strip()

        return render_template('page_viewer.html', 
                               judul=display_title, 
                               content=display_content)
    else:
        print(f"Halaman dengan ID {page_id} tidak ditemukan di database.")
        return "Halaman tidak ditemukan.", 404

if __name__ == '__main__':
    print("-----------------------------------------------------")
    print("           Memulai Aplikasi Web Search Engine          ")
    print("-----------------------------------------------------")
    print("Pastikan database sudah terisi (jalankan src/crawler/simple_crawler.py terlebih dahulu!)")
    print(f"Aplikasi Flask akan berjalan di: http://127.0.0.1:8080/")
    print("Tekan CTRL+C untuk menghentikan server.")
    print("-----------------------------------------------------")
    app.run(debug=True, port=8080)
