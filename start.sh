#!/bin/bash
# Script de démarrage pour Render avec SQLite

echo "🚀 Démarrage de l'application REED..."

# Créer les dossiers nécessaires
mkdir -p static/uploads
mkdir -p instance

# Restaurer la base de données depuis Google Drive si disponible
echo "📥 Tentative de restauration de la base de données..."
python restore_from_drive.py

# Initialiser la base de données si elle n'existe pas
if [ ! -f "instance/amicale.db" ] || [ ! -s "instance/amicale.db" ]; then
    echo "📦 Création d'une nouvelle base de données..."
    python create_tables.py
fi

# Vérifier et mettre à jour la structure de la base
echo "🔧 Vérification de la structure de la base..."
python ensure_db.py

# Démarrer l'application Flask avec Gunicorn
echo "🌐 Démarrage de Gunicorn..."
gunicorn wsgi:app --bind 0.0.0.0:10000 --workers 1 --timeout 120 &

# Démarrer le keep-alive en arrière-plan
echo "⚡ Démarrage du système de keep-alive..."
python keep_alive.py &

# Attendre que les processus se terminent
wait

echo "✅ Application démarrée avec succès !"