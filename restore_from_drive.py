#!/usr/bin/env python3
"""Script pour restaurer la base depuis Google Drive au démarrage"""

import os
import sys
from backup_to_drive import restore

if __name__ == '__main__':
    # Créer le dossier instance s'il n'existe pas
    os.makedirs('instance', exist_ok=True)
    
    # Restaurer la base
    success = restore()
    
    if success:
        print("✅ Base de données restaurée avec succès")
    else:
        print("ℹ️ Aucun backup trouvé, création d'une nouvelle base")