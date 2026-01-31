import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from database import StudentRequest

def migrate():
    """Ajouter la colonne region_universitaire à la table existante"""
    with app.app_context():
        try:
            # Pour PostgreSQL, nous devons utiliser ALTER TABLE
            # SQLAlchemy n'a pas de méthode native pour modifier les tables
            # Nous allons créer une nouvelle table et migrer les données
            
            print("Création d'une table temporaire...")
            
            # Créer une table temporaire avec la nouvelle structure
            temp_table_name = 'student_request_temp'
            
            # Vérifier si la colonne existe déjà
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('student_request')]
            
            if 'region_universitaire' in columns:
                print("La colonne region_universitaire existe déjà")
                return
            
            print("Migration des données...")
            
            # Migration simple: ajouter la colonne avec une valeur par défaut
            with db.engine.connect() as conn:
                # Pour SQLite
                if 'sqlite' in str(db.engine.url):
                    conn.execute(text('''
                        ALTER TABLE student_request 
                        ADD COLUMN region_universitaire VARCHAR(100) DEFAULT 'Dakar' NOT NULL
                    '''))
                # Pour PostgreSQL
                elif 'postgresql' in str(db.engine.url):
                    conn.execute(text('''
                        ALTER TABLE student_request 
                        ADD COLUMN region_universitaire VARCHAR(100) NOT NULL DEFAULT 'Dakar'
                    '''))
                
                conn.commit()
            
            print("✓ Migration réussie")
            
        except Exception as e:
            print(f"✗ Erreur migration: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    migrate()