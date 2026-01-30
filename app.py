import os
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
import requests

from config import Config
from database import db, StudentRequest

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Create necessary directories
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('instance', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def init_database():
    """Initialiser la base de données"""
    with app.app_context():
        db.create_all()
        print("✓ Base de données initialisée")

# Fonction SendGrid améliorée avec timeout
def send_email_sendgrid(to_email, subject, body, from_email=None):
    """Envoyer un email via SendGrid API v3"""
    try:
        api_key = app.config['SENDGRID_API_KEY']
        if not api_key:
            print("✗ SendGrid API Key non configurée")
            return False
        
        if from_email is None:
            from_email = app.config['MAIL_DEFAULT_SENDER']
            if not from_email:
                print("✗ Expéditeur non configuré")
                return False
        
        # URL de l'API SendGrid
        url = "https://api.sendgrid.com/v3/mail/send"
        
        # Headers avec l'API Key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Données JSON pour SendGrid
        data = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject
                }
            ],
            "from": {"email": from_email},
            "content": [
                {
                    "type": "text/plain",
                    "value": body
                }
            ]
        }
        
        # Envoyer la requête avec timeout
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code in [200, 202]:
            print(f"✓ Email envoyé à {to_email}")
            return True
        else:
            print(f"✗ Erreur SendGrid ({response.status_code}): {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout SendGrid pour {to_email}")
        return False
    except Exception as e:
        print(f"✗ Exception SendGrid pour {to_email}: {str(e)}")
        return False

# Fonction pour envoyer des emails en arrière-plan
def send_email_async(to_email, subject, body):
    """Envoyer un email en arrière-plan"""
    try:
        send_email_sendgrid(to_email, subject, body)
    except Exception as e:
        print(f"Erreur dans send_email_async: {str(e)}")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/formulaire', methods=['GET', 'POST'])
def formulaire():
    if request.method == 'POST':
        try:
            # Get form data
            nom = request.form.get('nom', '').strip()
            prenom = request.form.get('prenom', '').strip()
            adresse = request.form.get('adresse', '').strip()
            telephone = request.form.get('telephone', '').strip()
            email = request.form.get('email', '').strip().lower()
            
            # Validate required fields
            if not all([nom, prenom, adresse, telephone, email]):
                flash('Tous les champs sont obligatoires', 'error')
                return redirect(url_for('formulaire'))
            
            # Validate email format
            if '@' not in email or '.' not in email:
                flash('Format d\'email invalide', 'error')
                return redirect(url_for('formulaire'))
            
            # Validate phone number
            if not telephone.replace(' ', '').replace('+', '').isdigit():
                flash('Numéro de téléphone invalide', 'error')
                return redirect(url_for('formulaire'))
            
            # Create new student request
            new_request = StudentRequest(
                nom=nom,
                prenom=prenom,
                adresse=adresse,
                telephone=telephone,
                email=email,
                status='pending'
            )
            
            # Handle file uploads
            files_required = {
                'certificat_inscription': 'certificat_inscription',
                'certificat_residence': 'certificat_residence', 
                'demande_manuscrite': 'demande_manuscrite',
                'carte_membre_reed': 'carte_membre_reed',
                'copie_cni': 'copie_cni'
            }
            
            # Vérifier d'abord tous les fichiers
            for field, file_key in files_required.items():
                file = request.files.get(file_key)
                if not file or file.filename == '':
                    flash(f'Le fichier {field.replace("_", " ")} est requis', 'error')
                    return redirect(url_for('formulaire'))
                
                if not allowed_file(file.filename):
                    flash(f'Le fichier {field.replace("_", " ")} doit être au format PDF, PNG ou JPG', 'error')
                    return redirect(url_for('formulaire'))
            
            # Sauvegarder la demande d'abord
            db.session.add(new_request)
            db.session.flush()  # Get the ID without committing
            
            # Ensuite sauvegarder les fichiers
            for field, file_key in files_required.items():
                file = request.files.get(file_key)
                if file and file.filename and allowed_file(file.filename):
                    # Utiliser un nom de fichier simple
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = secure_filename(f"{new_request.id}_{field}.{ext}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Sauvegarder le fichier
                    file.save(filepath)
                    setattr(new_request, field, filename)
            
            # Commit toutes les données
            db.session.commit()
            
            # Envoyer l'email de confirmation en arrière-plan
            try:
                send_confirmation_email(email, nom, prenom, new_request.id)
            except Exception as email_error:
                print(f"Erreur programmation email: {email_error}")
                # Ne pas bloquer l'utilisateur si l'email échoue
            
            flash('Votre demande a été soumise avec succès!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de la soumission: {str(e)}")
            flash('Une erreur est survenue. Veuillez réessayer.', 'error')
            return redirect(url_for('formulaire'))
    
    return render_template('form.html')

def send_confirmation_email(to_email, nom, prenom, request_id):
    """Envoyer un email de confirmation à l'étudiant"""
    subject = "Confirmation de réception de votre demande"
    message = f"""Cher(e) {prenom} {nom},

Nous accusons réception de votre demande d'adhésion à l'Amicale des Étudiants (N°{request_id}).

Votre dossier est en cours de traitement et vous serez notifié(e) par email dès qu'une décision sera prise.

Nous vous remercions pour votre confiance.

Cordialement,
La Commission Sociale REED
Amicale des Étudiants
"""
    
    try:
        # Envoyer en arrière-plan
        thread = threading.Thread(
            target=send_email_async,
            args=(to_email, subject, message)
        )
        thread.daemon = True
        thread.start()
        print(f"✓ Email de confirmation programmé pour {to_email}")
        
    except Exception as email_error:
        print(f"✗ Erreur d'envoi d'email: {email_error}")

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # Utilisez les variables d'environnement
        admin_username = app.config['ADMIN_USERNAME']
        admin_password = app.config['ADMIN_PASSWORD']
        
        if username == admin_username and password == admin_password:
            session['admin_logged_in'] = True
            session.permanent = True
            flash('Connexion réussie!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Identifiants incorrects', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash('Veuillez vous connecter', 'error')
        return redirect(url_for('admin_login'))
    
    try:
        requests = StudentRequest.query.order_by(StudentRequest.date_submitted.desc()).all()
        pending_count = StudentRequest.query.filter_by(status='pending').count()
        approved_count = StudentRequest.query.filter_by(status='approved').count()
        rejected_count = StudentRequest.query.filter_by(status='rejected').count()
        
        return render_template('admin_dashboard.html', 
                             requests=requests,
                             pending_count=pending_count,
                             approved_count=approved_count,
                             rejected_count=rejected_count)
    except Exception as e:
        print(f"Erreur dashboard: {str(e)}")
        flash('Erreur de chargement du tableau de bord', 'error')
        return render_template('admin_dashboard.html', 
                             requests=[],
                             pending_count=0,
                             approved_count=0,
                             rejected_count=0)

@app.route('/admin/view/<int:request_id>')
def view_request(request_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        student_request = StudentRequest.query.get_or_404(request_id)
        return render_template('view_request.html', request=student_request)
    except Exception as e:
        flash('Demande non trouvée', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_status/<int:request_id>', methods=['POST'])
def update_status(request_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        student_request = StudentRequest.query.get_or_404(request_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Données JSON requises'}), 400
        
        status = data.get('status')
        notes = data.get('notes', '')
        
        if status in ['pending', 'approved', 'rejected']:
            old_status = student_request.status
            student_request.status = status
            student_request.admin_notes = notes
            student_request.date_processed = datetime.utcnow()
            db.session.commit()
            
            # Envoyer un email à l'étudiant si le statut change
            if old_status != status:
                send_status_email(student_request, status, notes)
            
            return jsonify({'success': True, 'message': 'Statut mis à jour'})
        else:
            return jsonify({'error': 'Statut invalide'}), 400
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def send_status_email(student, status, notes):
    """Envoyer un email à l'étudiant concernant le statut de sa demande"""
    if not student.email:
        return
    
    if status == 'approved':
        subject = "Félicitations ! Votre demande d'adhésion a été acceptée"
        message = f"""Cher(e) {student.prenom} {student.nom},

Nous avons le plaisir de vous informer que votre demande d'adhésion à l'Amicale des Étudiants (ID: {student.id}) a été approuvée.

Bienvenue dans notre communauté !

"""
    elif status == 'rejected':
        subject = "Décision concernant votre demande d'adhésion"
        message = f"""Cher(e) {student.prenom} {student.nom},

Après examen de votre demande d'adhésion (ID: {student.id}), nous regrettons de vous informer qu'elle n'a pas pu être acceptée pour le moment.

"""
    else:
        subject = "Mise à jour sur votre demande d'adhésion"
        message = f"""Cher(e) {student.prenom} {student.nom},

Votre demande d'adhésion (ID: {student.id}) est actuellement en cours de traitement par notre équipe.

Nous vous contacterons dès que nous aurons une décision.

"""
    
    if notes:
        message += f"\nNote: {notes}\n"
    
    message += """
Merci pour votre compréhension.

Cordialement,
La Commission Sociale REED
Amicale des Étudiants
"""
    
    try:
        # Envoyer en arrière-plan
        thread = threading.Thread(
            target=send_email_async,
            args=(student.email, subject, message)
        )
        thread.daemon = True
        thread.start()
        print(f"✓ Email de statut programmé pour {student.email}")
    except Exception as e:
        print(f"✗ Erreur d'envoi d'email de statut: {e}")

@app.route('/admin/send_email', methods=['POST'])
def send_email():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Données JSON requises'}), 400
        
        recipient_type = data.get('recipient_type', 'all')
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        custom_emails = data.get('custom_emails', [])
        selected_ids = data.get('selected_ids', [])
        
        if not subject or not message:
            return jsonify({'error': 'Sujet et message sont requis'}), 400
        
        # Récupérer les destinataires
        emails_list = []
        recipients = []
        
        try:
            if recipient_type == 'approved':
                recipients = StudentRequest.query.filter_by(status='approved').all()
                emails_list = [s.email for s in recipients if s.email]
            elif recipient_type == 'rejected':
                recipients = StudentRequest.query.filter_by(status='rejected').all()
                emails_list = [s.email for s in recipients if s.email]
            elif recipient_type == 'pending':
                recipients = StudentRequest.query.filter_by(status='pending').all()
                emails_list = [s.email for s in recipients if s.email]
            elif recipient_type == 'selected' and selected_ids:
                recipients = StudentRequest.query.filter(StudentRequest.id.in_(selected_ids)).all()
                emails_list = [s.email for s in recipients if s.email]
            elif recipient_type == 'custom' and custom_emails:
                emails_list = [email.strip() for email in custom_emails if email.strip()]
                recipients = []  # Pas de données étudiant pour emails personnalisés
            else:
                recipients = StudentRequest.query.all()
                emails_list = [s.email for s in recipients if s.email]
        except Exception as db_error:
            print(f"Erreur DB: {str(db_error)}")
            return jsonify({'error': 'Erreur base de données'}), 500
        
        # Filtrer les emails valides
        valid_emails = [email for email in emails_list if email and '@' in email and '.' in email]
        
        if not valid_emails:
            return jsonify({'error': 'Aucun destinataire valide trouvé'}), 400
        
        # Limiter à 10 emails pour éviter les limites
        valid_emails = valid_emails[:10]
        
        # Envoyer les emails en arrière-plan
        sent_count = 0
        
        for email in valid_emails:
            try:
                # Personnaliser le message si possible
                personalized_message = message
                if recipient_type in ['approved', 'rejected', 'pending', 'selected', 'all'] and recipients:
                    student = next((s for s in recipients if s.email == email), None)
                    if student:
                        personalized_message = message.replace('{nom}', student.nom or '')
                        personalized_message = personalized_message.replace('{prenom}', student.prenom or '')
                        personalized_message = personalized_message.replace('{id}', str(student.id))
                        if student.date_submitted:
                            personalized_message = personalized_message.replace('{date}', student.date_submitted.strftime('%d/%m/%Y'))
                
                # Envoyer en arrière-plan
                thread = threading.Thread(
                    target=send_email_async,
                    args=(email, subject, personalized_message)
                )
                thread.daemon = True
                thread.start()
                sent_count += 1
                
                # Petite pause pour éviter le rate limiting
                time.sleep(0.3)
                    
            except Exception as e:
                print(f"Erreur pour {email}: {str(e)}")
        
        # Préparer la réponse
        response_data = {
            'success': True, 
            'message': f'Envoi lancé pour {sent_count} email(s).',
            'sent_count': sent_count,
            'total_count': len(valid_emails)
        }
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Erreur générale send_email: {str(e)}")
        return jsonify({'error': 'Erreur interne du serveur'}), 500

@app.route('/test-sendgrid')
def test_sendgrid():
    """Route pour tester SendGrid"""
    try:
        test_email = "commissionsociale.reed@gmail.com"
        subject = "Test SendGrid"
        message = "Test réussi si vous recevez ce message."
        
        success = send_email_sendgrid(test_email, subject, message)
        
        if success:
            return "✓ Test SendGrid réussi"
        else:
            return "✗ Test SendGrid échoué"
    
    except Exception as e:
        return f"Erreur: {str(e)}"

@app.route('/admin/test-email', methods=['GET', 'POST'])
def admin_test_email():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            success = send_email_sendgrid(
                email, 
                "Test d'email", 
                "Ceci est un email de test."
            )
            
            if success:
                flash('✓ Test envoyé avec succès', 'success')
            else:
                flash('✗ Échec de l\'envoi', 'error')
        
        return redirect(url_for('admin_test_email'))
    
    return '''
    <div style="padding: 20px; max-width: 500px; margin: 0 auto;">
        <h2>Tester SendGrid</h2>
        <form method="POST">
            <input type="email" name="email" placeholder="email@exemple.com" required style="width:100%;padding:8px;margin:10px 0;">
            <button type="submit" style="padding:10px 20px;">Envoyer test</button>
        </form>
    </div>
    '''

@app.route('/admin/api/students')
def api_students():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        students = StudentRequest.query.all()
        students_data = []
        for student in students:
            students_data.append({
                'id': student.id,
                'nom': student.nom,
                'prenom': student.prenom,
                'email': student.email,
                'status': student.status
            })
        return jsonify(students_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/stats')
def api_stats():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        stats = {
            'total': StudentRequest.query.count(),
            'approved': StudentRequest.query.filter_by(status='approved').count(),
            'rejected': StudentRequest.query.filter_by(status='rejected').count(),
            'pending': StudentRequest.query.filter_by(status='pending').count()
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/debug')
def debug():
    info = {
        'database': 'OK' if db else 'ERROR',
        'upload_folder': os.path.exists(app.config['UPLOAD_FOLDER']),
        'sendgrid_key': 'SET' if app.config['SENDGRID_API_KEY'] else 'NOT SET',
        'sender': app.config['MAIL_DEFAULT_SENDER']
    }
    return jsonify(info) 

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Déconnexion réussie', 'success')
    return redirect(url_for('admin_login'))

# Gestion des erreurs
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"Erreur 500: {str(e)}")
    return render_template('500.html'), 500

# Point d'entrée
if __name__ == '__main__':
    init_database()
    print("\n" + "="*60)
    print("APPLICATION PRÊTE")
    print("="*60)
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print(f"SendGrid: {'✓' if app.config['SENDGRID_API_KEY'] else '✗'}")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)