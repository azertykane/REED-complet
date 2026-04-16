#!/bin/bash
# Script de démarrage pour Render avec SQLite

echo "🚀 Démarrage de l'application REED..."

# Créer les dossiers nécessaires
mkdir -p static/uploads
mkdir -p instance

# Initialiser la base de données
echo "📦 Initialisation de la base de données SQLite..."
python create_tables.py

# Démarrer l'application Flask avec Gunicorn
echo "🌐 Démarrage de Gunicorn..."
gunicorn wsgi:app --bind 0.0.0.0:10000 --workers 1 --timeout 120 &

# Démarrer le keep-alive en arrière-plan
echo "⚡ Démarrage du système de keep-alive..."
python keep_alive.py &

# Attendre que les processus se terminent
wait

echo "✅ Application démarrée avec succès !"