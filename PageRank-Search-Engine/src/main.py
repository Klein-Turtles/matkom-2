import os
import sys
from urllib.parse import urlparse # Tetap dibutuhkan untuk urlparse jika digunakan di tempat lain, atau bisa dihapus jika tidak.

# Tambahkan path ke folder src agar modul-modul di dalamnya bisa diimpor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'database')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'pagerank')))
# Untuk config.py, path-nya harus ke utils yang ada di root project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils')))


from db_manager import DBManager
# Mengimpor modul crawl_website dan populate_database dihapus karena tidak lagi digunakan di sini.
from pagerank_calculator import calculate_pagerank

def run_pagerank_calculation():
    """
    Menjalankan proses perhitungan PageRank berdasarkan data yang sudah ada di database.
    """
    db_manager = DBManager()
    db_manager.connect()
    if not db_manager.connection:
        print("Gagal terhubung ke database. Proses perhitungan PageRank dibatalkan.")
        return False # Mengindikasikan kegagalan

    try:
        # Pastikan tabel ada.
        db_manager.create_tables()
        
        print("\n--- Memulai Perhitungan PageRank ---")
        calculate_pagerank(db_manager)

        print("\nProses perhitungan PageRank selesai.")
        return True # Mengindikasikan keberhasilan
    except Exception as e:
        print(f"Terjadi error selama proses perhitungan PageRank: {e}")
        return False
    finally:
        db_manager.close_connection()

def search_engine_cli():
    """
    Menyediakan antarmuka Command Line Interface (CLI) untuk pencarian.
    """
    db_manager = DBManager()
    db_manager.connect()
    if not db_manager.connection:
        print("Gagal terhubung ke database. Fungsi pencarian tidak tersedia.")
        return

    print("\n--- Selamat Datang di Search Engine Sederhana ---")
    print("Ketik 'exit' untuk keluar.")

    while True:
        query = input("\nMasukkan kata kunci pencarian: ").strip()
        if query.lower() == 'exit':
            break
        if not query:
            continue

        results = db_manager.search_pages_by_keyword(query)

        if results:
            print(f"\nDitemukan {len(results)} hasil untuk '{query}':")
            for i, result in enumerate(results):
                print(f"  {i+1}. URL: {result['url']}")
                print(f"    PageRank Score: {result['pagerank_score']:.6f}")
                # Tampilkan cuplikan konten (misalnya 100 karakter pertama)
                snippet = result['content'][:100] + ('...' if len(result['content']) > 100 else '')
                print(f"    Konten: {snippet}")
        else:
            print(f"Tidak ada hasil ditemukan untuk '{query}'.")

    db_manager.close_connection()
    print("\nTerima kasih telah menggunakan search engine.")

if __name__ == '__main__':
    # Konfigurasi URL dan batasan crawling dihapus dari sini karena crawling tidak lagi dilakukan di main.py
    
    print("--- Memulai Proses Perhitungan PageRank ---")
    # Panggilan ke fungsi yang baru, tanpa parameter crawling
    pagerank_successful = run_pagerank_calculation()

    if pagerank_successful:
        print("\n--- Memulai Antarmuka Pencarian ---")
        search_engine_cli()
    else:
        print("\nProses perhitungan PageRank gagal, tidak dapat memulai pencarian CLI.")
