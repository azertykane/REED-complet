#!/usr/bin/env python3
"""Script à exécuter avant chaque déploiement sur Render"""

import os
import sys
from backup_to_drive import backup

if __name__ == '__main__':
    print("📤 Sauvegarde de la base avant déploiement...")
    
    if os.path.exists('instance/amicale.db'):
        success = backup()
        if success:
            print("✅ Backup effectué avec succès")
        else:
            print("⚠️ Erreur lors du backup")
    else:
        print("ℹ️ Aucune base de données à sauvegarder")