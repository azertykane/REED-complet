#!/usr/bin/env python3
"""Script pour ajouter les colonnes date_naissance et lieu_naissance"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            if 'student_request' not in inspector.get_table_names():
                print("La table student_request n'existe pas. Création...")
                db.create_all()
                print("✓ Tables créées")
                return
            
            columns = [col['name'] for col in inspector.get_columns('student_request')]
            print(f"Colonnes existantes: {columns}")
            
            modifications = 0
            
            with db.engine.connect() as conn:
                # Ajouter date_naissance
                if 'date_naissance' not in columns:
                    if 'sqlite' in str(db.engine.url):
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN date_naissance VARCHAR(20)'))
                    else:
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN date_naissance VARCHAR(20)'))
                    print("✓ Colonne 'date_naissance' ajoutée")
                    modifications += 1
                else:
                    print("• Colonne 'date_naissance' existe déjà")
                
                # Ajouter lieu_naissance
                if 'lieu_naissance' not in columns:
                    if 'sqlite' in str(db.engine.url):
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN lieu_naissance VARCHAR(200)'))
                    else:
                        conn.execute(text('ALTER TABLE student_request ADD COLUMN lieu_naissance VARCHAR(200)'))
                    print("✓ Colonne 'lieu_naissance' ajoutée")
                    modifications += 1
                else:
                    print("• Colonne 'lieu_naissance' existe déjà")
                
                conn.commit()
            
            if modifications > 0:
                print(f"\n✅ Migration terminée! {modifications} colonne(s) ajoutée(s)")
            else:
                print("\n✅ Aucune modification nécessaire")
            
            # Afficher les colonnes finales
            final_columns = [col['name'] for col in inspector.get_columns('student_request')]
            print(f"\n📋 Structure finale: {final_columns}")
            
        except Exception as e:
            print(f"✗ Erreur migration: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    print("="*50)
    print("MIGRATION - Ajout date_naissance et lieu_naissance")
    print("="*50)
    migrate()