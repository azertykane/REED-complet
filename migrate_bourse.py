#!/usr/bin/env python3
"""Script pour ajouter les colonnes categorie et etablissement"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from database import StudentRequest
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('student_request')]
            
            with db.engine.connect() as conn:
                # Ajouter colonne categorie
                if 'categorie' not in columns:
                    if 'sqlite' in str(db.engine.url):
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN categorie VARCHAR(20) DEFAULT "etudiant" NOT NULL'))
                    else:
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN categorie VARCHAR(20) NOT NULL DEFAULT "etudiant"'))
                    print("✓ Colonne 'categorie' ajoutée")
                
                # Ajouter colonne etablissement
                if 'etablissement' not in columns:
                    if 'sqlite' in str(db.engine.url):
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN etablissement VARCHAR(200) DEFAULT "" NOT NULL'))
                    else:
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN etablissement VARCHAR(200) NOT NULL DEFAULT ""'))
                    print("✓ Colonne 'etablissement' ajoutée")
                
                # Ajouter colonne bulletin_s2 si nécessaire
                if 'bulletin_s2' not in columns:
                    if 'sqlite' in str(db.engine.url):
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN bulletin_s2 VARCHAR(300)'))
                    else:
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN bulletin_s2 VARCHAR(300)'))
                    print("✓ Colonne 'bulletin_s2' ajoutée")
                
                conn.commit()
            
            print("✓ Migration terminée avec succès")
            
        except Exception as e:
            print(f"✗ Erreur migration: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    migrate()