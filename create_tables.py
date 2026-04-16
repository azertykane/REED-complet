#!/usr/bin/env python3
"""
Script pour initialiser la base de données avec les nouveaux modèles
"""

import os
import sys
from flask import Flask
from config import Config
from database import db, StudentRequest, ApplicationStatus

def create_app():
    """Créer l'application Flask"""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

def init_database():
    """Initialiser la base de données"""
    app = create_app()
    
    with app.app_context():
        try:
            # Créer toutes les tables
            db.create_all()
            print("✓ Base de données initialisée avec succès")
            
            # Créer l'enregistrement ApplicationStatus par défaut si inexistant
            app_status = ApplicationStatus.query.first()
            if not app_status:
                app_status = ApplicationStatus(
                    logement_open=False,
                    bourse_open=False
                )
                db.session.add(app_status)
                db.session.commit()
                print("✓ Statut des applications initialisé (fermé par défaut)")
            else:
                print("✓ Statut des applications déjà existant")
                
            # Afficher les statistiques
            total_requests = StudentRequest.query.count()
            print(f"✓ Total des demandes existantes: {total_requests}")
            
        except Exception as e:
            print(f"✗ Erreur lors de l'initialisation: {str(e)}")
            db.session.rollback()
            return False
    
    return True

if __name__ == '__main__':
    print("Initialisation de la base de données...")
    print("=" * 50)
    
    success = init_database()
    
    print("=" * 50)
    if success:
        print("✓ Initialisation terminée avec succès")
        sys.exit(0)
    else:
        print("✗ Échec de l'initialisation")
        sys.exit(1)