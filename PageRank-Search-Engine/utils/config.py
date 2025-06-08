# search_engine_project/utils/config.py
import os
from dotenv import load_dotenv

# Muat variabel lingkungan dari file .env
load_dotenv()

# Konfigurasi database, diambil dari variabel lingkungan
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# Parameter PageRank (bisa diubah nanti jika diperlukan)
PAGERANK_DAMPING_FACTOR = 0.85
PAGERANK_MAX_ITERATIONS = 100
PAGERANK_TOLERANCE = 1e-6