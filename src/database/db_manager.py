import mysql.connector
from mysql.connector import Error
import os

# Nama database yang akan digunakan (pastikan database ini sudah dibuat di server MySQL Anda)
DB_NAME = 'engine'

class DBManager:
    """
    Manages database connections and operations for the search engine.
    Uses MySQL.
    """
    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self):
        """Establishes a connection to the MySQL database."""
        try:
            self.connection = mysql.connector.connect(
                host="localhost", # GANTI DENGAN HOST MYSQL ANDA (misal: "127.0.0.1")
                user="root", # GANTI DENGAN USERNAME MYSQL ANDA
                password="", # GANTI DENGAN PASSWORD MYSQL ANDA
                database="engine" # Nama database yang akan digunakan
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor()
                print(f"Connected to MySQL database: {DB_NAME}")
                return True
            else:
                print("Failed to connect to MySQL database.")
                self.connection = None
                return False
        except Error as e:
            print(f"Database connection error: {e}")
            self.connection = None
            return False

    def close_connection(self):
        """Closes the database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.connection = None
            print("Database connection closed.")

    def create_tables(self):
        """
        Creates the 'pages' and 'links' tables if they don't exist,
        based on the provided SQL schema (for MySQL).
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot create tables: No database connection.")
            return False
        try:
            # Use the database
            self.cursor.execute(f"USE {DB_NAME};")

            # Table for pages, storing URL, content, and PageRank score
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS pages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    url VARCHAR(255) UNIQUE NOT NULL,
                    content TEXT,
                    pagerank_score FLOAT DEFAULT 0.0
                )
            ''')
            # Table for links between pages
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS links (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_page_id INT NOT NULL,
                    target_page_id INT NOT NULL,
                    FOREIGN KEY (source_page_id) REFERENCES pages(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_page_id) REFERENCES pages(id) ON DELETE CASCADE
                )
            ''')
            self.connection.commit()
            print("Tables checked/created successfully.")
            return True
        except Error as e:
            print(f"Error creating tables: {e}")
            return False

    def insert_page(self, url, content):
        """
        Inserts a new page into the 'pages' table.
        If the URL already exists, it returns the existing page's ID.
        Returns the ID of the inserted/existing page, or None on error.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot insert page: No database connection.")
            return None
        try:
            self.cursor.execute("INSERT INTO pages (url, content) VALUES (%s, %s)", (url, content))
            self.connection.commit()
            return self.cursor.lastrowid # Returns the ID of the last inserted row
        except mysql.connector.IntegrityError as e:
            if e.errno == 1062: # Duplicate entry for UNIQUE constraint
                # Retrieve the ID of the existing page
                self.cursor.execute("SELECT id FROM pages WHERE url = %s", (url,))
                existing_id = self.cursor.fetchone()
                print(f"Warning: Page with URL '{url}' already exists. Returning existing ID: {existing_id[0] if existing_id else 'N/A'}.")
                return existing_id[0] if existing_id else None
            else:
                print(f"Error inserting page: {e}")
                return None
        except Error as e:
            print(f"Error inserting page: {e}")
            return None

    def insert_link(self, source_page_id, target_page_id):
        """
        Inserts a link between two pages into the 'links' table.
        Returns True on success, False on failure.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot insert link: No database connection.")
            return False
        try:
            self.cursor.execute("INSERT INTO links (source_page_id, target_page_id) VALUES (%s, %s)",
                                (source_page_id, target_page_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error inserting link ({source_page_id} -> {target_page_id}): {e}")
            return False

    def get_all_documents(self):
        """
        Retrieves all documents (pages) from the database, including their PageRank scores.
        Returns a list of dictionaries, or an empty list on error.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot retrieve all documents: No database connection.")
            return []
        try:
            self.cursor.execute("SELECT id, url, content, pagerank_score FROM pages")
            rows = self.cursor.fetchall()
            documents = []
            for row in rows:
                documents.append({
                    'id': row[0],
                    'url': row[1],
                    'content': row[2],
                    'pagerank_score': row[3]
                })
            return documents
        except Error as e:
            print(f"Error retrieving all documents: {e}")
            return []

    def get_links(self):
        """
        Retrieves all links (source_page_id, target_page_id) from the database.
        Returns a list of tuples, or an empty list on error.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot retrieve links: No database connection.")
            return []
        try:
            self.cursor.execute("SELECT source_page_id, target_page_id FROM links")
            return self.cursor.fetchall()
        except Error as e:
            print(f"Error retrieving links: {e}")
            return []

    def update_pagerank_score(self, page_id, score):
        """
        Updates the PageRank score for a given page ID.
        Returns True on success, False on failure.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot update PageRank: No database connection.")
            return False
        try:
            self.cursor.execute("UPDATE pages SET pagerank_score = %s WHERE id = %s", (score, page_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating PageRank for ID {page_id}: {e}")
            return False

    def search_pages_by_keyword(self, keyword):
        """
        Performs a basic keyword search on page content and URL,
        ordering results by PageRank score in descending order.
        Returns a list of dictionaries, or an empty list on error.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot search pages: No database connection.")
            return []
        try:
            # Using LIKE for basic keyword search (case-insensitive)
            # Orders by pagerank_score to prioritize more important pages
            search_pattern = f"%{keyword.lower()}%"
            self.cursor.execute(
                "SELECT id, url, content, pagerank_score FROM pages WHERE LOWER(content) LIKE %s OR LOWER(url) LIKE %s ORDER BY pagerank_score DESC",
                (search_pattern, search_pattern)
            )
            rows = self.cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'url': row[1],
                    'content': row[2],
                    'pagerank_score': row[3]
                })
            return results
        except Error as e:
            print(f"Error searching pages by keyword: {e}")
            return []

    def get_document_by_id(self, page_id):
        """
        Retrieves a single document by its ID.
        Returns a dictionary representing the page, or None if not found or on error.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot get document by ID: No database connection.")
            return None
        try:
            self.cursor.execute("SELECT id, url, content, pagerank_score FROM pages WHERE id = %s", (page_id,))
            row = self.cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'url': row[1],
                    'content': row[2],
                    'pagerank_score': row[3]
                }
            return None
        except Error as e:
            print(f"Error retrieving document by ID {page_id}: {e}")
            return None

    def clear_tables(self):
        """
        Clears all data from the 'links' and 'pages' tables.
        Use with caution, as this deletes all crawled data.
        Returns True on success, False on failure.
        """
        if not self.connection or not self.connection.is_connected():
            print("Cannot clear tables: No database connection.")
            return False
        try:
            # Note: FOREIGN_KEY_CHECKS might need to be temporarily disabled for clearing parent table first
            # but DELETE FROM handles dependencies if ON DELETE CASCADE is set up correctly.
            self.cursor.execute("DELETE FROM links")
            self.cursor.execute("DELETE FROM pages")
            self.connection.commit()
            print("All tables cleared successfully.")
            return True
        except Error as e:
            print(f"Error clearing tables: {e}")
            return False

