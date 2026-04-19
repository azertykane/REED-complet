#!/usr/bin/env python3
"""
Script de sauvegarde automatique sur Google Drive
À exécuter avant chaque déploiement ou périodiquement
"""

import os
import sys
import json
import requests
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.exceptions import RefreshError

# Configuration
DB_PATH = 'instance/amicale.db'
FOLDER_ID = '1nINSpI1qvje58znkMUspQaLGOrHbyo-h'  # Votre dossier Google Drive

def get_credentials():
    """Obtenir les credentials Google Drive"""
    creds = None
    
    # Chemin vers le fichier token
    token_path = 'token.json'
    creds_path = 'credentials.json'
    
    # Charger les credentials existants
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/drive.file'])
    
    # Si pas de credentials valides, demander authentification
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("Session expirée, veuillez vous reconnecter")
                os.remove(token_path)
                creds = None
        
        if not creds:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_path, ['https://www.googleapis.com/auth/drive.file'])
            creds = flow.run_local_server(port=0)
            
            # Sauvegarder les credentials
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
    
    return creds

def upload_to_drive(creds, file_path, folder_id):
    """Uploader un fichier sur Google Drive"""
    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Nom du fichier avec date
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'amicale_backup_{timestamp}.db'
        
        # Métadonnées du fichier
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, mimetype='application/x-sqlite3', resumable=True)
        
        # Upload
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        print(f"✅ Backup sauvegardé sur Google Drive: {file_name}")
        print(f"   ID du fichier: {file.get('id')}")
        
        # Nettoyer les anciens backups (garder seulement les 10 derniers)
        cleanup_old_backups(service, folder_id)
        
        return file.get('id')
        
    except Exception as e:
        print(f"❌ Erreur upload: {str(e)}")
        return None

def cleanup_old_backups(service, folder_id, keep=10):
    """Supprimer les anciens backups (garder les 10 plus récents)"""
    try:
        # Lister les fichiers dans le dossier
        results = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/x-sqlite3'",
            orderBy='createdTime desc',
            pageSize=keep+5,
            fields='files(id, name, createdTime)'
        ).execute()
        
        files = results.get('files', [])
        
        # Supprimer les fichiers en trop
        if len(files) > keep:
            for file in files[keep:]:
                service.files().delete(fileId=file['id']).execute()
                print(f"   Suppression ancien backup: {file['name']}")
                
    except Exception as e:
        print(f"Erreur nettoyage: {str(e)}")

def download_latest_backup(creds, folder_id, destination_path):
    """Télécharger la dernière sauvegarde depuis Google Drive"""
    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Récupérer le dernier fichier
        results = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/x-sqlite3'",
            orderBy='createdTime desc',
            pageSize=1,
            fields='files(id, name)'
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print("Aucun backup trouvé sur Google Drive")
            return False
        
        latest = files[0]
        
        # Télécharger le fichier
        request = service.files().get_media(fileId=latest['id'])
        
        with open(destination_path, 'wb') as f:
            f.write(request.execute())
        
        print(f"✅ Backup restauré depuis Google Drive: {latest['name']}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur téléchargement: {str(e)}")
        return False

def backup():
    """Fonction principale de backup"""
    if not os.path.exists(DB_PATH):
        print(f"Base de données non trouvée: {DB_PATH}")
        return False
    
    creds = get_credentials()
    if creds:
        return upload_to_drive(creds, DB_PATH, FOLDER_ID)
    return False

def restore():
    """Fonction principale de restauration"""
    creds = get_credentials()
    if creds:
        return download_latest_backup(creds, FOLDER_ID, DB_PATH)
    return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'backup':
            backup()
        elif sys.argv[1] == 'restore':
            restore()
        else:
            print("Usage: python backup_to_drive.py [backup|restore]")
    else:
        backup()