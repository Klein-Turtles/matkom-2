import numpy as np
import sys
import os

# Tambahkan path ke folder database agar db_manager bisa diimpor
# os.path.dirname(__file__) -> src/pagerank
# os.path.join(..., '..') -> src/
# os.path.join(..., '..', 'database') -> src/database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))
# Tambahkan path ke folder utils agar config bisa diimpor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'utils')))

from db_manager import DBManager
# Pastikan file config.py ada di folder utils/
# dan mendefinisikan PAGERANK_DAMPING_FACTOR, PAGERANK_MAX_ITERATIONS, PAGERANK_TOLERANCE
from config import PAGERANK_DAMPING_FACTOR, PAGERANK_MAX_ITERATIONS, PAGERANK_TOLERANCE

def calculate_pagerank(db_manager):
    """
    Menghitung skor PageRank untuk semua halaman dalam database.

    Args:
        db_manager (DBManager): Instance dari DBManager untuk interaksi database.

    Returns:
        dict: Kamus berisi {page_id: pagerank_score}.
    """
    print("\n--- Memulai Perhitungan PageRank ---")

    # Menggunakan db_manager.get_all_documents() sesuai definisi di db_manager.py
    pages = db_manager.get_all_documents()
    # Menggunakan db_manager.get_links() sesuai definisi di db_manager.py
    links = db_manager.get_links()

    if not pages:
        print("Tidak ada halaman di database untuk dihitung PageRank. Proses dihentikan.")
        return {}

    N = len(pages)
    if N == 0:
        print("Jumlah halaman nol. Tidak ada PageRank untuk dihitung.")
        return {}

    # Buat pemetaan ID database ke indeks matriks (0-N-1) dan sebaliknya
    # Pastikan 'id' ada di setiap dictionary 'page'
    id_to_idx = {page['id']: i for i, page in enumerate(pages)}
    idx_to_id = {i: page['id'] for i, page in enumerate(pages)}

    # Inisialisasi matriks transisi A (Adjacency Matrix)
    # A[i, j] = 1 jika ada link dari j ke i (j adalah sumber, i adalah target)
    A = np.zeros((N, N))

    # Hitung out-degree (jumlah link keluar) untuk setiap halaman
    out_degrees = np.zeros(N)

    # Catatan: Fungsi get_links() di db_manager.py mengembalikan list of tuples (source_id, target_id)
    # Anda perlu menyesuaikan cara mengakses elemen link di sini.
    for source_id, target_id in links: # Ubah cara mengakses link
        # Pastikan ID sumber dan target ada di pemetaan
        if source_id in id_to_idx and target_id in id_to_idx:
            source_idx = id_to_idx[source_id]
            target_idx = id_to_idx[target_id]
            
            # Matriks A: A[i][j] berarti link dari j ke i
            # Untuk PageRank, kolom j merepresentasikan halaman sumber
            # Jadi, A[target_idx][source_idx] = 1
            A[target_idx, source_idx] = 1
            out_degrees[source_idx] += 1
        else:
            # Ini akan memberikan peringatan jika ada link ke halaman yang tidak ada di pages
            print(f"Warning: Link dari ID {source_id} ke ID {target_id} merujuk ke halaman yang tidak ditemukan di dokumen yang di-crawl. Diabaikan.")

    # Bangun Matriks Transisi M
    # M[i, j] = 1 / (out-degree of j) jika ada link dari j ke i
    M = np.zeros((N, N))
    for j in range(N): # Iterasi kolom (halaman sumber)
        if out_degrees[j] > 0:
            # Normalisasi kolom jika ada link keluar
            M[:, j] = A[:, j] / out_degrees[j]
        else:
            # Jika dangling node (halaman tanpa link keluar),
            # distribusikan probabilitas secara merata ke semua node.
            # Ini penting agar matriks tetap stokastik.
            M[:, j] = 1.0 / N

    # Bangun Matriks Google (G) dengan Damping Factor
    # G = alpha * M + (1 - alpha) * (1/N) * J
    # J adalah matriks N x N yang semua elemennya 1
    # Matriks E di sini adalah matriks N x N yang semua elemennya 1/N
    E = np.full((N, N), 1.0 / N)
    G = PAGERANK_DAMPING_FACTOR * M + (1 - PAGERANK_DAMPING_FACTOR) * E

    # Inisialisasi vektor PageRank
    # PR_0 = vektor kolom yang semua elemennya 1/N
    pr = np.full((N, 1), 1.0 / N)

    print(f"Memulai iterasi PageRank dengan {N} halaman...")
    # Power Iteration
    for i in range(PAGERANK_MAX_ITERATIONS):
        pr_new = np.dot(G, pr)
        # Hitung perubahan (norma L1) untuk cek konvergensi
        change = np.sum(np.abs(pr_new - pr))
        # print(f"   Iterasi {i+1}: Perubahan = {change:.8f}") # Untuk debug, bisa di-comment
        if change < PAGERANK_TOLERANCE:
            print(f"Konvergen pada iterasi {i+1}.")
            break
        pr = pr_new
    else:
        print(f"Mencapai maksimum iterasi ({PAGERANK_MAX_ITERATIONS}) tanpa konvergensi penuh.")

    # Normalisasi terakhir (pastikan jumlah semua PR = 1, meskipun sudah dinormalisasi di G)
    pr = pr / np.sum(pr)

    # Simpan hasil PageRank ke database
    pagerank_results = {}
    print("\n--- Menyimpan Hasil PageRank ke Database ---")
    for i in range(N):
        page_id = idx_to_id[i]
        score = float(pr[i][0])
        db_manager.update_pagerank_score(page_id, score)
        pagerank_results[page_id] = score
    
    print("Perhitungan PageRank selesai dan hasil disimpan ke database.")
    return pagerank_results

# Blok __main__ ini untuk testing standalone.
# Akan dipanggil dari main.py atau app.py dalam skenario aplikasi penuh.
if __name__ == '__main__':
    db_manager = DBManager()
    db_manager.connect()

    if not db_manager.connection:
        print("Gagal terhubung ke database. Tidak dapat melakukan pengujian PageRank mandiri.")
    else:
        # Untuk pengujian, pastikan ada data di DB (jalankan src/crawler/simple_crawler.py lebih dulu)
        pages_in_db = db_manager.get_all_documents() # Menggunakan get_all_documents
        if not pages_in_db:
            print("Database kosong. Mohon jalankan 'simple_crawler.py' terlebih dahulu untuk mengisi data.")
        else:
            print(f"Ditemukan {len(pages_in_db)} halaman di database.")
            pageranks = calculate_pagerank(db_manager)
            print("\nHasil PageRank:")
            # Ambil kembali data pages dari database untuk mendapatkan URL terbaru
            # ini penting karena data 'pages_in_db' di awal bisa jadi tidak update
            # jika pagerank dihitung di run_pagerank_calculation() terpisah
            updated_pages = db_manager.get_all_documents()
            for page_id, score in pageranks.items():
                page_info = next((p for p in updated_pages if p['id'] == page_id), None)
                url = page_info['url'] if page_info else f"ID: {page_id}"
                print(f"   {url}: {score:.6f}")

    db_manager.close_connection()
