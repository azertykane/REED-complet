# export_donnees_complet_urllib.py
import os
import shutil
import psycopg2
import urllib.request
import urllib.error
from datetime import datetime
import csv
import json
import ssl

# Configuration
DB_URL = "postgresql://reed_user:CXZqRSHicAeR1K31bQbYYIxQ97YE4xai@dpg-d5t8aqggjchc73eecff0-a.virginia-postgres.render.com/reed"
BASE_URL = "https://reed-site.onrender.com/uploads/"

# Dossier de destination
DOSSIER_BASE = "exports_reed_complet"
DOSSIER_DOCUMENTS = os.path.join(DOSSIER_BASE, "documents")

# Ignorer les erreurs SSL (si nécessaire)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

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

def telecharger_fichier(url, destination):
    """Télécharge un fichier depuis une URL en utilisant urllib"""
    try:
        # Configuration de la requête
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Créer une requête avec headers
        req = urllib.request.Request(url, headers=headers)
        
        # Télécharger le fichier
        with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
            with open(destination, 'wb') as out_file:
                out_file.write(response.read())
        
        return True, response.headers.get_content_type()
        
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URL Error: {e.reason}"
    except Exception as e:
        return False, str(e)

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

def telecharger_tous_les_documents(donnees, colnames):
    """Télécharge tous les documents depuis Render"""
    
    # Index des colonnes
    index_map = {col: i for i, col in enumerate(colnames)}
    
    # Statistiques
    stats = {
        'total': len(donnees),
        'documents_trouves': 0,
        'documents_telecharges': 0,
        'documents_manquants': 0,
        'erreurs': []
    }
    
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
    
    print("\n📥 Téléchargement des documents depuis Render...")
    
    for row in donnees:
        dossier_id = row[index_map['id']]
        nom = row[index_map['nom']]
        prenom = row[index_map['prenom']]
        region = row[index_map['region_universitaire']]
        
        # Nettoyer le nom de région pour le dossier
        nom_region = region.replace(' ', '_').replace('-', '_').replace("'", "").replace('/', '_')
        
        # Créer le chemin du dossier pour cette région et cet ID
        chemin_region = os.path.join(DOSSIER_DOCUMENTS, nom_region)
        chemin_dossier = os.path.join(chemin_region, str(dossier_id))
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
            'documents_telecharges': []
        }
        
        print(f"\n📁 Dossier {dossier_id} - {prenom} {nom}")
        
        # Télécharger chaque document
        for doc_type in types_documents:
            nom_fichier = row[index_map[doc_type]]
            
            if nom_fichier:
                stats['documents_trouves'] += 1
                
                # Construire l'URL complète
                url_fichier = BASE_URL + nom_fichier
                
                # Déterminer l'extension
                extension = os.path.splitext(nom_fichier)[1]
                if not extension:
                    extension = '.pdf'  # Par défaut
                
                # Chemin de destination
                chemin_dest = os.path.join(chemin_dossier, f"{doc_type}{extension}")
                
                # Télécharger le fichier
                print(f"  📥 Téléchargement {doc_type}...", end=" ")
                print(f"({url_fichier})")
                
                succes, message = telecharger_fichier(url_fichier, chemin_dest)
                
                if succes:
                    stats['documents_telecharges'] += 1
                    dossier_info['documents_telecharges'].append({
                        'type': doc_type,
                        'fichier': f"{doc_type}{extension}",
                        'url': url_fichier
                    })
                    print(f"✅ OK")
                else:
                    stats['documents_manquants'] += 1
                    stats['erreurs'].append(f"{dossier_id}/{doc_type}: {message}")
                    print(f"❌ Erreur: {message}")
            else:
                print(f"  ⚠️ {doc_type}: Non fourni")
        
        # Sauvegarder les infos du dossier
        with open(os.path.join(chemin_dossier, 'infos.json'), 'w', encoding='utf-8') as f:
            json.dump(dossier_info, f, ensure_ascii=False, indent=2)
        
        # Ajouter aux régions pour l'index
        regions[region].append(dossier_info)
    
    return regions, stats

def generer_index_html(regions, stats):
    """Génère une page HTML d'index"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Export complet des demandes REED</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .stats {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }}
        .stat-card {{ background: #667eea; color: white; padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-card.green {{ background: #28a745; }}
        .stat-card.orange {{ background: #ffc107; color: black; }}
        .stat-card.red {{ background: #dc3545; }}
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
        .success {{ color: #28a745; }}
        .error {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Export complet des demandes REED</h1>
        <p>Date d'export: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        
        <div class="stats">
            <h3>Statistiques</h3>
            <div class="stat-grid">
                <div class="stat-card">
                    <h4>Total dossiers</h4>
                    <p style="font-size: 24px;">{stats['total']}</p>
                </div>
                <div class="stat-card green">
                    <h4>Documents trouvés</h4>
                    <p style="font-size: 24px;">{stats['documents_trouves']}</p>
                </div>
                <div class="stat-card green">
                    <h4>Téléchargés</h4>
                    <p style="font-size: 24px;">{stats['documents_telecharges']}</p>
                </div>
                <div class="stat-card red">
                    <h4>Manquants/Erreurs</h4>
                    <p style="font-size: 24px;">{stats['documents_manquants']}</p>
                </div>
            </div>
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
            
            nb_docs = len(dossier['documents_telecharges'])
            
            html_content += f"""
            <div class="dossier">
                <div class="info">
                    <strong>#{dossier['id']}</strong> - 
                    {dossier['prenom']} {dossier['nom']}
                    <span class="statut {statut}">{statut_fr}</span>
                    <span class="statut {'green' if nb_docs > 0 else 'orange'}">{nb_docs}/5 documents</span>
                </div>
                <div class="info">
                    📧 {dossier['email']} | 📞 {dossier['telephone']}
                </div>
                <div class="info">
                    📅 {dossier['date_soumission']}
                </div>
                <div class="documents">
                    <strong>Documents téléchargés:</strong><br>
            """
            
            doc_names = {
                'certificat_inscription': '📜 Certificat inscription',
                'certificat_residence': '🏠 Certificat résidence',
                'copie_cni': '🆔 Copie CNI',
                'demande_manuscrite': '✍️ Demande manuscrite',
                'carte_membre_reed': '🎫 Carte membre REED'
            }
            
            for doc in dossier['documents_telecharges']:
                doc_type = doc['type']
                doc_file = doc['fichier']
                nom_region = dossier['region'].replace(' ', '_').replace('-', '_').replace("'", "").replace('/', '_')
                
                html_content += f"""
                    <a href="documents/{nom_region}/{dossier['id']}/{doc_file}" target="_blank">
                        {doc_names.get(doc_type, doc_type)}
                    </a><br>
                """
            
            html_content += """
                </div>
            </div>
            """
        
        html_content += """
            </div>
        </div>
        """
    
    # Ajouter la section des erreurs si nécessaire
    if stats['erreurs']:
        html_content += """
        <div class="region">
            <h2 style="background: #dc3545;">⚠️ Erreurs de téléchargement</h2>
            <div class="dossiers">
                <ul>
        """
        for erreur in stats['erreurs'][:50]:
            html_content += f"<li class='error'>{erreur}</li>"
        if len(stats['erreurs']) > 50:
            html_content += f"<li>... et {len(stats['erreurs']) - 50} autres erreurs</li>"
        html_content += """
                </ul>
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
    print("🚀 Début de l'exportation COMPLÈTE des données (avec téléchargement des fichiers)...")
    
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
        
        # Télécharger tous les documents
        regions, stats = telecharger_tous_les_documents(donnees, colnames)
        
        # Générer l'index HTML
        generer_index_html(regions, stats)
        
        print(f"\n✅ Export COMPLET terminé avec succès!")
        print(f"📁 Les fichiers sont dans le dossier: {DOSSIER_BASE}")
        print(f"📊 Fichier CSV: student_requests_[date].csv")
        print(f"📂 Documents téléchargés: {stats['documents_telecharges']}/{stats['documents_trouves']}")
        print(f"🌐 Index HTML: {DOSSIER_BASE}/index.html")
        
        print(f"\n📊 Résumé par région:")
        for region, dossiers in sorted(regions.items()):
            print(f"   • {region}: {len(dossiers)} dossier(s)")
        
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()