# export_donnees_final.py
import os
import psycopg2
from datetime import datetime
import csv
import json
import base64

# Configuration
DB_URL = "postgresql://reed_user:CXZqRSHicAeR1K31bQbYYIxQ97YE4xai@dpg-d5t8aqggjchc73eecff0-a.virginia-postgres.render.com/reed"

# Dossier de destination
DOSSIER_BASE = "exports_reed_final"
DOSSIER_DOCUMENTS = os.path.join(DOSSIER_BASE, "documents")

def creer_structure_dossiers():
    """Crée la structure de dossiers nécessaire"""
    os.makedirs(DOSSIER_BASE, exist_ok=True)
    os.makedirs(DOSSIER_DOCUMENTS, exist_ok=True)
    print(f"✅ Dossiers créés dans {DOSSIER_BASE}")

def connexion_bd():
    """Établit la connexion à la base de données"""
    try:
        conn = psycopg2.connect(DB_URL)
        print("✅ Connexion à la base de données réussie")
        return conn
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return None

def recuperer_tous_les_dossiers(conn):
    """Récupère tous les dossiers avec leurs informations"""
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            id, nom, prenom, adresse, telephone, email,
            region_universitaire, status, date_submitted,
            certificat_inscription, certificat_residence,
            copie_cni, demande_manuscrite, carte_membre_reed
        FROM student_request
        ORDER BY region_universitaire, nom, prenom
        """
        
        cursor.execute(query)
        resultats = cursor.fetchall()
        
        colnames = [desc[0] for desc in cursor.description]
        cursor.close()
        
        print(f"✅ {len(resultats)} dossiers trouvés")
        return resultats, colnames
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données: {e}")
        return None, None

def exporter_donnees_csv(donnees, colnames):
    """Exporte les données au format CSV"""
    fichier_csv = os.path.join(DOSSIER_BASE, f"student_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    with open(fichier_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(colnames)
        writer.writerows(donnees)
    
    print(f"✅ Données exportées dans {fichier_csv}")
    return fichier_csv

def creer_fichiers_placeholder(donnees, colnames):
    """
    Crée des fichiers placeholder pour visualiser la structure
    et génère un rapport avec les instructions pour récupérer les vrais fichiers
    """
    
    # Index des colonnes
    index_map = {col: i for i, col in enumerate(colnames)}
    
    # Types de documents
    types_documents = [
        'certificat_inscription',
        'certificat_residence',
        'copie_cni',
        'demande_manuscrite',
        'carte_membre_reed'
    ]
    
    # Dictionnaire pour organiser par région
    regions = {}
    
    # Statistiques
    fichiers_manquants = []
    
    print("\n📁 Création de la structure des dossiers...")
    
    for row in donnees:
        dossier_id = str(row[index_map['id']])
        nom = row[index_map['nom']]
        prenom = row[index_map['prenom']]
        region = row[index_map['region_universitaire']]
        
        # Nettoyer le nom de région pour le dossier
        nom_region = region.replace(' ', '_').replace('-', '_').replace("'", "").replace('/', '_')
        
        # Créer le chemin du dossier pour cette région et cet ID
        chemin_region = os.path.join(DOSSIER_DOCUMENTS, nom_region)
        chemin_dossier = os.path.join(chemin_region, dossier_id)
        os.makedirs(chemin_dossier, exist_ok=True)
        
        # Ajouter à la structure regions pour l'index
        if region not in regions:
            regions[region] = []
        
        # Créer les infos du dossier
        dossier_info = {
            'id': dossier_id,
            'nom': nom,
            'prenom': prenom,
            'adresse': row[index_map['adresse']],
            'telephone': row[index_map['telephone']],
            'email': row[index_map['email']],
            'region': region,
            'statut': row[index_map['status']],
            'date_soumission': str(row[index_map['date_submitted']]) if row[index_map['date_submitted']] else None,
            'documents': {}
        }
        
        print(f"\n📁 Dossier {dossier_id} - {prenom} {nom}")
        
        # Créer un placeholder pour chaque document
        for doc_type in types_documents:
            nom_fichier = row[index_map[doc_type]]
            
            if nom_fichier:
                # Déterminer l'extension
                extension = os.path.splitext(nom_fichier)[1]
                if not extension:
                    extension = '.pdf'
                
                # Chemin du fichier placeholder
                chemin_placeholder = os.path.join(chemin_dossier, f"{doc_type}{extension}")
                
                # Créer un fichier texte qui explique comment récupérer le vrai fichier
                with open(chemin_placeholder.replace(extension, '.txt'), 'w', encoding='utf-8') as f:
                    f.write(f"""FICHIER MANQUANT
====================
Dossier ID: {dossier_id}
Étudiant: {prenom} {nom}
Type de document: {doc_type}
Nom du fichier original: {nom_fichier}

COMMENT RÉCUPÉRER CE FICHIER:
-----------------------------
1. Connectez-vous à votre compte Render (https://dashboard.render.com)
2. Allez dans votre service Web "reed-site"
3. Ouvrez le "Shell" ou "Console"
4. Exécutez ces commandes :

   cd /opt/render/project/src
   find . -name "{nom_fichier}" -type f

5. Si le fichier est trouvé, téléchargez-le avec :

   cat /chemin/vers/le/fichier/{nom_fichier}

6. Copiez le contenu base64 qui s'affiche et décodez-le

OU ALTERNATIVEMENT:
------------------
Utilisez SCP ou SFTP pour télécharger tous les fichiers du dossier uploads/
""")
                
                # Ajouter aux statistiques
                fichiers_manquants.append({
                    'dossier_id': dossier_id,
                    'etudiant': f"{prenom} {nom}",
                    'region': region,
                    'type': doc_type,
                    'fichier': nom_fichier
                })
                
                dossier_info['documents'][doc_type] = {
                    'nom_fichier': nom_fichier,
                    'placeholder_cree': True
                }
                
                print(f"  📝 Placeholder créé pour {doc_type} ({nom_fichier})")
            else:
                print(f"  ⚠️ {doc_type}: Non fourni")
        
        # Sauvegarder les infos du dossier
        with open(os.path.join(chemin_dossier, 'infos.json'), 'w', encoding='utf-8') as f:
            json.dump(dossier_info, f, ensure_ascii=False, indent=2)
        
        # Ajouter aux régions pour l'index
        regions[region].append(dossier_info)
    
    # Générer un rapport des fichiers manquants
    rapport_path = os.path.join(DOSSIER_BASE, 'fichiers_manquants.txt')
    with open(rapport_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RAPPORT DES FICHIERS MANQUANTS À RÉCUPÉRER SUR RENDER\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total des dossiers: {len(donnees)}\n")
        f.write(f"Total des fichiers manquants: {len(fichiers_manquants)}\n\n")
        
        f.write("LISTE DES FICHIERS:\n")
        f.write("-"*80 + "\n")
        
        for fichier in fichiers_manquants:
            f.write(f"Dossier {fichier['dossier_id']} - {fichier['etudiant']}\n")
            f.write(f"  {fichier['type']}: {fichier['fichier']}\n")
            f.write(f"  Région: {fichier['region']}\n\n")
    
    print(f"\n✅ Rapport généré: {rapport_path}")
    
    return regions, fichiers_manquants

def generer_index_html(regions, fichiers_manquants):
    """Génère une page HTML d'index"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Export des demandes REED</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .warning {{ background: #ffc107; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .region {{ margin-bottom: 30px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .region h2 {{ background: #667eea; color: white; padding: 15px; margin: 0; }}
        .dossiers {{ padding: 15px; }}
        .dossier {{ margin-bottom: 15px; padding: 15px; border-left: 4px solid #764ba2; background: #f8f9fa; border-radius: 4px; }}
        .dossier:hover {{ background: #e9ecef; }}
        .statut {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; }}
        .pending {{ background: #ffc107; color: #000; }}
        .approved {{ background: #28a745; color: white; }}
        .rejected {{ background: #dc3545; color: white; }}
        .documents {{ margin-top: 10px; padding: 10px; background: white; border-radius: 4px; }}
        .documents a {{ color: #667eea; text-decoration: none; margin-right: 15px; }}
        .documents a:hover {{ text-decoration: underline; }}
        .missing {{ color: #dc3545; font-style: italic; }}
        .instructions {{ background: #e7f3ff; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Export des demandes REED</h1>
        <p>Date d'export: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        
        <div class="warning">
            <strong>⚠️ IMPORTANT:</strong> Les fichiers n'ont pas pu être téléchargés automatiquement car ils ne sont pas accessibles publiquement.
            <br>Consultez le fichier <code>fichiers_manquants.txt</code> pour les instructions de récupération.
        </div>
        
        <div class="instructions">
            <h3>📥 Comment récupérer les vrais fichiers :</h3>
            <ol>
                <li>Connectez-vous à <a href="https://dashboard.render.com" target="_blank">Render Dashboard</a></li>
                <li>Allez dans votre service "reed-site"</li>
                <li>Ouvrez le "Shell" (console)</li>
                <li>Exécutez : <code>ls -la /opt/render/project/src/uploads/</code> pour voir les fichiers</li>
                <li>Pour télécharger un fichier : <code>cat /opt/render/project/src/uploads/nom_du_fichier</code></li>
                <li>Copiez le contenu et sauvegardez-le avec le bon nom</li>
            </ol>
            <p><strong>Total des fichiers à récupérer : {len(fichiers_manquants)}</strong></p>
        </div>
    """
    
    for region, dossiers in sorted(regions.items()):
        html_content += f"""
        <div class="region">
            <h2>📍 {region} ({len(dossiers)} dossier{'s' if len(dossiers) > 1 else ''})</h2>
            <div class="dossiers">
        """
        
        for dossier in dossiers:
            statut = dossier['statut']
            statut_fr = {
                'pending': 'En attente',
                'approved': 'Approuvé',
                'rejected': 'Refusé'
            }.get(statut, statut)
            
            html_content += f"""
            <div class="dossier">
                <div class="info">
                    <strong>#{dossier['id']}</strong> - 
                    {dossier['prenom']} {dossier['nom']}
                    <span class="statut {statut}">{statut_fr}</span>
                </div>
                <div class="info">
                    📧 {dossier['email']} | 📞 {dossier['telephone']}
                </div>
                <div class="info">
                    📅 {dossier['date_soumission']}
                </div>
                <div class="documents">
                    <strong>Documents (placeholders):</strong><br>
                    <span class="missing">Les fichiers doivent être récupérés depuis Render</span>
                </div>
            </div>
            """
        
        html_content += """
            </div>
        </div>
        """
    
    html_content += """
    </div>
</body>
</html>
    """
    
    with open(os.path.join(DOSSIER_BASE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Index HTML généré dans {DOSSIER_BASE}/index.html")

def main():
    """Fonction principale"""
    print("🚀 Début de l'exportation des données...")
    
    creer_structure_dossiers()
    
    conn = connexion_bd()
    if not conn:
        return
    
    try:
        # Récupérer les données
        donnees, colnames = recuperer_tous_les_dossiers(conn)
        if not donnees:
            return
        
        print(f"\n📊 Colonnes trouvées: {', '.join(colnames)}")
        print(f"📋 {len(donnees)} enregistrements à traiter")
        
        # Exporter en CSV
        exporter_donnees_csv(donnees, colnames)
        
        # Créer la structure avec placeholders
        regions, fichiers_manquants = creer_fichiers_placeholder(donnees, colnames)
        
        # Générer l'index HTML
        generer_index_html(regions, fichiers_manquants)
        
        print(f"\n✅ Structure créée avec succès!")
        print(f"📁 Les dossiers sont dans: {DOSSIER_BASE}")
        print(f"📊 Fichier CSV: student_requests_[date].csv")
        print(f"📝 Rapport des fichiers: fichiers_manquants.txt")
        print(f"🌐 Index HTML: index.html")
        
        print(f"\n📊 Résumé par région:")
        for region, dossiers in sorted(regions.items()):
            print(f"   • {region}: {len(dossiers)} dossier(s)")
        
        print(f"\n📊 Statistiques:")
        print(f"   • Total dossiers: {len(donnees)}")
        print(f"   • Fichiers à récupérer: {len(fichiers_manquants)}")
        
        print(f"\n🔧 PROCHAINES ÉTAPES:")
        print(f"   1. Connectez-vous à https://dashboard.render.com")
        print(f"   2. Allez dans votre service 'reed-site'")
        print(f"   3. Ouvrez le 'Shell' et exécutez: ls -la /opt/render/project/src/uploads/")
        print(f"   4. Téléchargez chaque fichier manquant")
        
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()