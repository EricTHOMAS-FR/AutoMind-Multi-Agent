import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="amma_data.db"):
        """Initialise la connexion à la base de données SQLite."""
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        """Crée les tables nécessaires si elles n'existent pas déjà."""
        cursor = self.conn.cursor()
        
        # 1. Table des communications (Agent à Agent)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS internal_comms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                receiver TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. Table de la base de résolution (Publique, avec système de notation)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resolution_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_author TEXT,
                problem_description TEXT,
                solution_content TEXT,
                social_score INTEGER DEFAULT 5 CHECK(social_score >= 0 AND social_score <= 10),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. Table de la mémoire à long terme (Privée)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                note_content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()

    # ==========================================
    # MÉTHODES : COMMUNICATIONS INTERNES
    # ==========================================
    def send_message(self, sender, receiver, message):
        """Permet à un agent d'envoyer un message à un autre."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO internal_comms (sender, receiver, message) 
            VALUES (?, ?, ?)
        ''', (sender, receiver, message))
        self.conn.commit()

    def get_unread_messages(self, agent_name):
        """Récupère les messages non lus pour un agent et les marque comme lus."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, sender, message, timestamp 
            FROM internal_comms 
            WHERE receiver = ? AND is_read = 0
            ORDER BY timestamp ASC
        ''', (agent_name,))
        messages = cursor.fetchall()
        
        if messages:
            # Marquer comme lus
            msg_ids = [msg[0] for msg in messages]
            placeholders = ','.join('?' * len(msg_ids))
            cursor.execute(f'''
                UPDATE internal_comms 
                SET is_read = 1 
                WHERE id IN ({placeholders})
            ''', msg_ids)
            self.conn.commit()
            
        return [{"id": m[0], "sender": m[1], "message": m[2], "time": m[3]} for m in messages]

    # ==========================================
    # MÉTHODES : BASE DE RÉSOLUTION (Savoir partagé)
    # ==========================================
    def publish_solution(self, agent_author, problem, solution):
        """Publie une nouvelle solution trouvée par un agent."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO resolution_base (agent_author, problem_description, solution_content) 
            VALUES (?, ?, ?)
        ''', (agent_author, problem, solution))
        self.conn.commit()
        return cursor.lastrowid

    def rate_solution(self, solution_id, score_change):
        """
        Modifie la note d'une solution (+1 ou -1) après évaluation par un testeur.
        La note reste bloquée entre 0 et 10 grâce au CHECK SQL.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                UPDATE resolution_base 
                SET social_score = social_score + ? 
                WHERE id = ?
            ''', (score_change, solution_id))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Si on essaie de dépasser 10 ou descendre sous 0, on ignore l'erreur
            pass

    def search_solutions(self, keyword):
        """Recherche des solutions dans la base publique, triées par pertinence (note)."""
        cursor = self.conn.cursor()
        search_term = f"%{keyword}%"
        cursor.execute('''
            SELECT problem_description, solution_content, social_score 
            FROM resolution_base 
            WHERE problem_description LIKE ? OR solution_content LIKE ?
            ORDER BY social_score DESC
            LIMIT 5
        ''', (search_term, search_term))
        return cursor.fetchall()

    # ==========================================
    # MÉTHODES : MÉMOIRE LONG TERME (Privée)
    # ==========================================
    def save_private_note(self, agent_name, note):
        """Sauvegarde une réflexion personnelle de l'agent."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO long_term_memory (agent_name, note_content) 
            VALUES (?, ?)
        ''', (agent_name, note))
        self.conn.commit()

    def get_private_notes(self, agent_name, limit=5):
        """Récupère les dernières notes de l'agent."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT note_content, timestamp 
            FROM long_term_memory 
            WHERE agent_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (agent_name, limit))
        return cursor.fetchall()

# Petit test rapide pour vérifier que tout fonctionne si on exécute ce fichier seul
if __name__ == "__main__":
    db = DatabaseManager("test_amma.db")
    db.send_message("Alice_Code", "Bob_Test", "J'ai fini la fonction de tri.")
    messages = db.get_unread_messages("Bob_Test")
    print("Messages pour Bob :", messages)
    print("Test réussi ! La base de données est prête.")