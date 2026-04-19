#!/usr/bin/env python3
"""Script pour s'assurer que la base de données a toutes les colonnes nécessaires"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def ensure_database():
    """Vérifie et ajoute les colonnes manquantes"""
    with app.app_context():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            if 'student_request' not in inspector.get_table_names():
                print("Création des tables...")
                db.create_all()
                print("✓ Tables créées")
                return
            
            columns = [col['name'] for col in inspector.get_columns('student_request')]
            
            with db.engine.connect() as conn:
                # Ajouter region_universitaire
                if 'region_universitaire' not in columns:
                    conn.execute(text('ALTER TABLE student_request ADD COLUMN region_universitaire VARCHAR(100) DEFAULT "Dakar"'))
                    print("✓ region_universitaire ajoutée")
                
                # Ajouter categorie
                if 'categorie' not in columns:
                    conn.execute(text('ALTER TABLE student_request ADD COLUMN categorie VARCHAR(20) DEFAULT "etudiant"'))
                    print("✓ categorie ajoutée")
                
                # Ajouter etablissement
                if 'etablissement' not in columns:
                    conn.execute(text('ALTER TABLE student_request ADD COLUMN etablissement VARCHAR(200) DEFAULT ""'))
                    print("✓ etablissement ajoutée")
                
                # Ajouter bulletin_s2
                if 'bulletin_s2' not in columns:
                    conn.execute(text('ALTER TABLE student_request ADD COLUMN bulletin_s2 VARCHAR(300)'))
                    print("✓ bulletin_s2 ajoutée")
                
                # Ajouter request_type
                if 'request_type' not in columns:
                    conn.execute(text('ALTER TABLE student_request ADD COLUMN request_type VARCHAR(20) DEFAULT "logement"'))
                    print("✓ request_type ajoutée")
                
                conn.commit()
                
        except Exception as e:
            print(f"Erreur ensure_database: {str(e)}")

if __name__ == '__main__':
    ensure_database()
    print("Base de données prête !")