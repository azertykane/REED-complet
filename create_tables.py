#!/usr/bin/env python3
"""Script pour initialiser la base de données PostgreSQL"""
import os
import sys
from app import app, db

with app.app_context():
    try:
        print("Création des tables de la base de données...")
        db.create_all()
        print("✓ Tables créées avec succès!")
        
        # Vérifier la connexion
        from database import StudentRequest
        count = StudentRequest.query.count()
        print(f"✓ Base de données opérationnelle ({count} enregistrements)")
        
    except Exception as e:
        print(f"✗ Erreur: {str(e)}")
        sys.exit(1)