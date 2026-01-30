#!/bin/bash
# start.sh

# Créer les dossiers nécessaires
mkdir -p static/uploads instance

# Initialiser la base de données
python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Base de données initialisée')
"

# Démarrer l'application
exec gunicorn --bind 0.0.0.0:$PORT --timeout 120 --workers 2 app:app