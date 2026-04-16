#!/usr/bin/env python3
"""
Script pour maintenir l'application active sur Render avec SQLite
Envoie un ping interne toutes les 5 minutes pour éviter le sleep
"""

import time
import threading
import requests
import os
import sys

def get_app_url():
    """Récupère l'URL de l'application depuis les variables d'environnement Render"""
    # Sur Render, l'URL est disponible via RENDER_EXTERNAL_URL ou RENDER_SERVICE_NAME
    external_url = os.environ.get('RENDER_EXTERNAL_URL')
    if external_url:
        return external_url
    
    # Si on est en local, retourne localhost
    return 'http://localhost:5000'

def ping_app():
    """Envoie un ping à l'application pour la maintenir active"""
    try:
        base_url = get_app_url()
        ping_url = f"{base_url}/ping"
        
        # Envoie un GET à la route /ping
        response = requests.get(ping_url, timeout=10)
        
        if response.status_code == 200:
            print(f"✓ Ping réussi à {ping_url} - Statut: {response.status_code}")
            return True
        else:
            print(f"⚠ Ping échoué à {ping_url} - Statut: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Erreur lors du ping: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ Erreur inattendue: {str(e)}")
        return False

def start_keep_alive(interval_minutes=5):
    """Démarre le thread de keep-alive"""
    def ping_loop():
        while True:
            try:
                # Attendre l'intervalle spécifié (en secondes)
                time.sleep(interval_minutes * 60)
                
                # Envoyer le ping
                ping_app()
                
            except KeyboardInterrupt:
                print("\nArrêt du keep-alive...")
                break
            except Exception as e:
                print(f"Erreur dans le loop de keep-alive: {str(e)}")
                time.sleep(60)  # Attendre 1 minute avant de réessayer
    
    # Créer et démarrer le thread
    ping_thread = threading.Thread(target=ping_loop, daemon=True)
    ping_thread.start()
    
    print(f"✓ Keep-alive démarré - Ping toutes les {interval_minutes} minutes")
    return ping_thread

if __name__ == '__main__':
    print("Démarrage du système de keep-alive...")
    print("=" * 50)
    
    # Démarrer le keep-alive avec un intervalle de 5 minutes
    start_keep_alive(5)
    
    # Garder le script en cours d'exécution
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt du keep-alive demandé par l'utilisateur")
        sys.exit(0)