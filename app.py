import os
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
import requests
import json

from config import Config
from database import db, StudentRequest, ApplicationStatus

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Create necessary directories
upload_folder = app.config['UPLOAD_FOLDER']
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('instance', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def init_database():
    """Initialiser la base de données"""
    with app.app_context():
        try:
            db.create_all()
            print("✓ Base de données initialisée")
        except Exception as e:
            print(f"✗ Erreur création base de données: {str(e)}")
            try:
                db.drop_all()
                db.create_all()
                print("✓ Base de données recréée")
            except Exception as e2:
                print(f"✗ Erreur grave: {str(e2)}")

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
        
        url = "https://api.sendgrid.com/v3/mail/send"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
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

@app.route('/information')
def information():
    return render_template('information.html')

# CORRECTION: Route formulaire logement avec vérification ouverture/fermeture
@app.route('/formulaire', methods=['GET', 'POST'])
def formulaire():
    # Vérifier si les demandes de logement sont ouvertes
    app_status = ApplicationStatus.query.first()
    logement_open = app_status.logement_open if app_status else False
    
    # Si formulaire fermé, afficher la page "fermé"
    if not logement_open:
        return render_template('form.html')  # Page avec message "Inscriptions Closes"
    
    # Sinon, traiter le formulaire normalement
    if request.method == 'POST':
        try:
            nom = request.form.get('nom', '').strip()
            prenom = request.form.get('prenom', '').strip()
            adresse = request.form.get('adresse', '').strip()
            telephone = request.form.get('telephone', '').strip()
            email = request.form.get('email', '').strip().lower()
            region_universitaire = request.form.get('region_universitaire', 'Dakar').strip()
            
            if not all([nom, prenom, adresse, telephone, email, region_universitaire]):
                flash('Tous les champs sont obligatoires', 'error')
                return redirect(url_for('formulaire'))
            
            if '@' not in email or '.' not in email:
                flash('Format d\'email invalide', 'error')
                return redirect(url_for('formulaire'))
            
            if not telephone.replace(' ', '').replace('+', '').isdigit():
                flash('Numéro de téléphone invalide', 'error')
                return redirect(url_for('formulaire'))
            
            new_request = StudentRequest(
                nom=nom,
                prenom=prenom,
                adresse=adresse,
                telephone=telephone,
                email=email,
                region_universitaire=region_universitaire,
                request_type='logement',
                status='pending'
            )
            
            files_required = {
                'certificat_inscription': 'certificat_inscription',
                'certificat_residence': 'certificat_residence', 
                'demande_manuscrite': 'demande_manuscrite',
                'carte_membre_reed': 'carte_membre_reed',
                'copie_cni': 'copie_cni'
            }
            
            for field, file_key in files_required.items():
                file = request.files.get(file_key)
                if not file or file.filename == '':
                    flash(f'Le fichier {field.replace("_", " ")} est requis', 'error')
                    return redirect(url_for('formulaire'))
                
                if not allowed_file(file.filename):
                    flash(f'Le fichier {field.replace("_", " ")} doit être au format PDF, PNG ou JPG', 'error')
                    return redirect(url_for('formulaire'))
            
            db.session.add(new_request)
            db.session.flush()
            
            for field, file_key in files_required.items():
                file = request.files.get(file_key)
                if file and file.filename and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = secure_filename(f"{new_request.id}_{field}.{ext}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    setattr(new_request, field, filename)
            
            db.session.commit()
            
            try:
                send_confirmation_email(email, nom, prenom, new_request.id)
            except Exception as email_error:
                print(f"Erreur programmation email: {email_error}")
            
            flash('Votre demande a été soumise avec succès!', 'success')
            return redirect(url_for('information'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de la soumission: {str(e)}")
            flash('Une erreur est survenue. Veuillez réessayer.', 'error')
            return redirect(url_for('formulaire'))
    
    regions_universitaires = [
        'Dakar', 'Thiès', 'Saint-Louis', 'Ziguinchor', 'Kolda',
        'Tambacounda', 'Kaolack', 'Fatick', 'Diourbel', 'Louga',
        'Matam', 'Kédougou', 'Sédhiou'
    ]
    return render_template('forms.html', regions_universitaires=regions_universitaires)

def send_confirmation_email(to_email, nom, prenom, request_id):
    """Envoyer un email de confirmation à l'étudiant"""
    subject = "Confirmation de réception de votre demande"
    message = f"""Cher(e) {prenom} {nom},

Nous accusons réception de votre demande de logement au sein des appartements du REED.

Votre dossier est en cours de traitement et vous serez notifié(e) par email dès qu'une décision sera prise.

Nous vous remercions pour votre confiance et n'oubliez pas de consulter vos emails section Spam.

Cordialement,
La Commission Sociale REED
"""
    
    try:
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
        
        regions_stats = {}
        regions = StudentRequest.query.with_entities(
            StudentRequest.region_universitaire,
            db.func.count(StudentRequest.id).label('count')
        ).group_by(StudentRequest.region_universitaire).all()
        
        for region, count in regions:
            regions_stats[region] = count
        
        return render_template('admin_dashboard.html', 
                             requests=requests,
                             pending_count=pending_count,
                             approved_count=approved_count,
                             rejected_count=rejected_count,
                             regions_stats=regions_stats)
        
    except Exception as e:
        print(f"Erreur dashboard: {str(e)}")
        flash('Erreur de chargement du tableau de bord', 'error')
        return render_template('admin_dashboard.html', 
                             requests=[],
                             pending_count=0,
                             approved_count=0,
                             rejected_count=0,
                             regions_stats={})

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

@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """Servir les fichiers uploadés depuis le dossier d'uploads"""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)
        
        if not os.path.exists(file_path):
            return "Fichier non trouvé", 404
        
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        print(f"Erreur serveur fichier: {str(e)}")
        return "Erreur serveur", 500

@app.route('/check-uploads')
def check_uploads():
    """Vérifier les fichiers dans le dossier uploads"""
    upload_folder = app.config['UPLOAD_FOLDER']
    files = []
    
    if os.path.exists(upload_folder):
        for f in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, f)
            if os.path.isfile(filepath):
                files.append({
                    'name': f,
                    'size': os.path.getsize(filepath),
                    'path': filepath,
                    'url': f'/uploads/{f}'
                })
    
    return jsonify({
        'upload_folder': upload_folder,
        'exists': os.path.exists(upload_folder),
        'files': files,
        'total': len(files)
    })

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
        subject = "Félicitations ! Votre demande a été acceptée"
        message = f"""Cher(e) {student.prenom} {student.nom},

Nous avons le plaisir de vous informer que votre demande a été approuvée.

Bienvenue dans notre communauté !

"""
    elif status == 'rejected':
        subject = "Décision concernant votre demande"
        message = f"""Cher(e) {student.prenom} {student.nom},

Après examen de votre demande, nous regrettons de vous informer qu'elle n'a pas pu être acceptée pour le moment.

"""
    else:
        subject = "Mise à jour sur votre demande"
        message = f"""Cher(e) {student.prenom} {student.nom},

Votre demande est actuellement en cours de traitement par notre équipe.

Nous vous contacterons dès que nous aurons une décision.

"""
    
    if notes:
        message += f"\nNote: {notes}\n"
    
    message += """
Merci pour votre compréhension.

Cordialement,
La Commission Sociale REED
"""
    
    try:
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
                recipients = []
            else:
                recipients = StudentRequest.query.all()
                emails_list = [s.email for s in recipients if s.email]
        except Exception as db_error:
            print(f"Erreur DB: {str(db_error)}")
            return jsonify({'error': 'Erreur base de données'}), 500
        
        valid_emails = [email for email in emails_list if email and '@' in email and '.' in email]
        
        if not valid_emails:
            return jsonify({'error': 'Aucun destinataire valide trouvé'}), 400
        
        valid_emails = valid_emails[:10]
        sent_count = 0
        
        for email in valid_emails:
            try:
                personalized_message = message
                if recipient_type in ['approved', 'rejected', 'pending', 'selected', 'all'] and recipients:
                    student = next((s for s in recipients if s.email == email), None)
                    if student:
                        personalized_message = message.replace('{nom}', student.nom or '')
                        personalized_message = personalized_message.replace('{prenom}', student.prenom or '')
                        personalized_message = personalized_message.replace('{id}', str(student.id))
                        if student.date_submitted:
                            personalized_message = personalized_message.replace('{date}', student.date_submitted.strftime('%d/%m/%Y'))
                
                thread = threading.Thread(
                    target=send_email_async,
                    args=(email, subject, personalized_message)
                )
                thread.daemon = True
                thread.start()
                sent_count += 1
                time.sleep(0.3)
                    
            except Exception as e:
                print(f"Erreur pour {email}: {str(e)}")
        
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

@app.route('/admin/download_report')
def download_report():
    """Générer un rapport PDF"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        p.setFont("Helvetica-Bold", 16)
        p.setFillColor(HexColor("#1E3A8A"))
        p.drawString(1*inch, height - 1*inch, "Rapport des Demandes - REED")
        
        p.setFont("Helvetica", 10)
        p.setFillColor(HexColor("#666666"))
        p.drawString(1*inch, height - 1.2*inch, f"Généré le: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        y_position = height - 2*inch
        
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(HexColor("#1E3A8A"))
        p.drawString(1*inch, y_position, "Statistiques:")
        
        y_position -= 0.25*inch
        p.setFont("Helvetica", 10)
        p.setFillColor(HexColor("#000000"))
        
        total = StudentRequest.query.count()
        pending = StudentRequest.query.filter_by(status='pending').count()
        approved = StudentRequest.query.filter_by(status='approved').count()
        rejected = StudentRequest.query.filter_by(status='rejected').count()
        
        stats = [
            f"Total des demandes: {total}",
            f"En attente: {pending}",
            f"Approuvées: {approved}",
            f"Rejetées: {rejected}"
        ]
        
        for stat in stats:
            p.drawString(1.2*inch, y_position, stat)
            y_position -= 0.2*inch
        
        y_position -= 0.3*inch
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(HexColor("#1E3A8A"))
        p.drawString(1*inch, y_position, "Liste des Demandes:")
        
        y_position -= 0.3*inch
        p.setFont("Helvetica", 8)
        
        p.setFillColor(HexColor("#FBBF24"))
        p.rect(1*inch, y_position - 0.1*inch, 6.5*inch, 0.25*inch, fill=1, stroke=0)
        p.setFillColor(HexColor("#000000"))
        headers = ["ID", "Nom", "Prénom", "Email", "Statut", "Date"]
        col_widths = [0.5, 1.5, 1.5, 2, 1, 1]
        
        x_position = 1*inch
        for header, width in zip(headers, col_widths):
            p.drawString(x_position + 0.1*inch, y_position, header)
            x_position += width*inch
        
        y_position -= 0.3*inch
        
        requests = StudentRequest.query.order_by(StudentRequest.date_submitted.desc()).all()
        for req in requests:
            if y_position < 1*inch:
                p.showPage()
                p.setFont("Helvetica", 8)
                y_position = height - 1*inch
            
            row_data = [
                str(req.id),
                req.nom,
                req.prenom,
                req.email[:20] + "..." if len(req.email) > 20 else req.email,
                req.status,
                req.date_submitted.strftime('%d/%m/%y') if req.date_submitted else ''
            ]
            
            x_position = 1*inch
            for data, width in zip(row_data, col_widths):
                p.drawString(x_position + 0.1*inch, y_position, str(data))
                x_position += width*inch
            
            y_position -= 0.2*inch
        
        p.save()
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"rapport_reed_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
    
    except Exception as e:
        flash(f'Erreur lors de la génération du rapport: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

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
                "Test d'email - REED", 
                "Ceci est un email de test depuis votre application sur Render."
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

@app.route('/admin/email_compose')
def email_compose():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    return render_template('email_compose.html')

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

@app.route('/admin/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    """Supprimer une demande"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        student_request = StudentRequest.query.get_or_404(request_id)
        
        files_to_delete = [
            student_request.certificat_inscription,
            student_request.certificat_residence,
            student_request.demande_manuscrite,
            student_request.carte_membre_reed,
            student_request.copie_cni
        ]
        
        for filename in files_to_delete:
            if filename:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        print(f"✓ Fichier supprimé: {filename}")
                    except Exception as e:
                        print(f"✗ Erreur suppression fichier {filename}: {str(e)}")
        
        db.session.delete(student_request)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Demande #{request_id} supprimée avec succès'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete_requests', methods=['POST'])
def delete_requests():
    """Supprimer plusieurs demandes"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Données JSON requises'}), 400
        
        request_ids = data.get('request_ids', [])
        
        if not request_ids:
            return jsonify({'error': 'Aucune demande sélectionnée'}), 400
        
        deleted_count = 0
        error_count = 0
        
        for request_id in request_ids:
            try:
                student_request = StudentRequest.query.get(request_id)
                if student_request:
                    files_to_delete = [
                        student_request.certificat_inscription,
                        student_request.certificat_residence,
                        student_request.demande_manuscrite,
                        student_request.carte_membre_reed,
                        student_request.copie_cni
                    ]
                    
                    for filename in files_to_delete:
                        if filename:
                            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            if os.path.exists(filepath):
                                os.remove(filepath)
                    
                    db.session.delete(student_request)
                    deleted_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"Erreur suppression demande {request_id}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} demande(s) supprimée(s)',
            'deleted_count': deleted_count,
            'error_count': error_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete_all_requests', methods=['POST'])
def delete_all_requests():
    """Supprimer toutes les demandes (ATTENTION: action irréversible)"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Non autorisé'}), 401
    
    try:
        data = request.get_json()
        if not data or not data.get('confirm'):
            return jsonify({'error': 'Confirmation requise'}), 400
        
        all_requests = StudentRequest.query.all()
        deleted_count = 0
        
        for student_request in all_requests:
            try:
                files_to_delete = [
                    student_request.certificat_inscription,
                    student_request.certificat_residence,
                    student_request.demande_manuscrite,
                    student_request.carte_membre_reed,
                    student_request.copie_cni
                ]
                
                for filename in files_to_delete:
                    if filename:
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                
                db.session.delete(student_request)
                deleted_count += 1
                
            except Exception as e:
                print(f"Erreur suppression demande {student_request.id}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Toutes les demandes ({deleted_count}) ont été supprimées',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/debug')
def debug():
    """Route de débogage"""
    info = {
        'database_configured': 'OK' if db else 'ERROR',
        'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
        'sendgrid_key_set': 'YES' if app.config['SENDGRID_API_KEY'] else 'NO',
        'sender_email': app.config['MAIL_DEFAULT_SENDER'],
        'database_url': app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...' if len(app.config['SQLALCHEMY_DATABASE_URI']) > 50 else app.config['SQLALCHEMY_DATABASE_URI']
    }
    return jsonify(info)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Déconnexion réussie', 'success')
    return redirect(url_for('admin_login'))

@app.route('/ping')
def ping():
    """Route pour le keep-alive"""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'REED-app'
    }), 200

@app.route('/health')
def health():
    """Route de santé"""
    try:
        StudentRequest.query.first()
        db_status = 'OK'
    except:
        db_status = 'ERROR'
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'REED-app'
    }), 200

@app.route('/admis')
def admis():
    """Affiche la liste des admis à partir du fichier JSON"""
    json_path = os.path.join(app.root_path, 'static', 'data', 'admis.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            admis_list = json.load(f)
        admis_list.sort(key=lambda x: x['nom'])
        return render_template('admis.html', admis=admis_list)
    except FileNotFoundError:
        return "Fichier des admis introuvable. Veuillez contacter l'administrateur.", 404
    except Exception as e:
        return f"Erreur lors du chargement des données : {str(e)}", 500

# CORRECTION: Route bourse - redirige vers formulaire si ouvert, sinon page fermée
@app.route('/bourse')
def bourse_info():
    """Page d'information sur les bourses"""
    app_status = ApplicationStatus.query.first()
    bourse_open = app_status.bourse_open if app_status else False
    
    if bourse_open:
        # Si ouvert, rediriger vers le formulaire
        return redirect(url_for('formulaire_bourse'))
    else:
        # Si fermé, afficher la page "fermé"
        return render_template('forms_bourse.html', bourse_open=bourse_open)

@app.route('/formulaire_bourse', methods=['GET', 'POST'])
def formulaire_bourse():
    """Formulaire de demande de bourse"""
    app_status = ApplicationStatus.query.first()
    if not app_status or not app_status.bourse_open:
        flash('Les demandes de bourses ne sont pas ouvertes pour le moment.', 'error')
        return redirect(url_for('bourse_info'))
    
    if request.method == 'POST':
        try:
            nom = request.form.get('nom', '').strip()
            prenom = request.form.get('prenom', '').strip()
            adresse = request.form.get('adresse', '').strip()
            telephone = request.form.get('telephone', '').strip()
            email = request.form.get('email', '').strip().lower()
            etablissement = request.form.get('etablissement', '').strip()  # NOUVEAU
            categorie = request.form.get('categorie', 'etudiant').strip()  # NOUVEAU
            
            if not all([nom, prenom, adresse, telephone, email, etablissement]):
                flash('Tous les champs sont obligatoires', 'error')
                return redirect(url_for('formulaire_bourse'))
            
            if '@' not in email or '.' not in email:
                flash('Format d\'email invalide', 'error')
                return redirect(url_for('formulaire_bourse'))
            
            if not telephone.replace(' ', '').replace('+', '').isdigit():
                flash('Numéro de téléphone invalide', 'error')
                return redirect(url_for('formulaire_bourse'))
            
            new_request = StudentRequest(
                nom=nom,
                prenom=prenom,
                adresse=adresse,
                telephone=telephone,
                email=email,
                etablissement=etablissement,  # NOUVEAU
                categorie=categorie,  # NOUVEAU
                request_type='bourse',
                status='pending'
            )
            
            # Gestion des fichiers selon la catégorie
            if categorie == 'etudiant':
                files_required = {
                    'demande_manuscrite': 'demande_manuscrite',
                    'certificat_inscription': 'certificat_inscription',
                    'copie_cni': 'copie_cni',
                    'certificat_residence': 'certificat_residence',
                    'carte_membre_reed': 'carte_membre_reed'
                }
            else:  # eleve
                files_required = {
                    'demande_manuscrite': 'demande_manuscrite',
                    'certificat_scolarite': 'certificat_scolarite',
                    'bulletin_s2': 'bulletin_s2',
                    'certificat_residence': 'certificat_residence',
                    'carte_membre_reed': 'carte_membre_reed'
                }
            
            # Vérifier tous les fichiers
            for field, file_key in files_required.items():
                file = request.files.get(file_key)
                if not file or file.filename == '':
                    flash(f'Le fichier {field.replace("_", " ")} est requis', 'error')
                    return redirect(url_for('formulaire_bourse'))
                
                if not allowed_file(file.filename):
                    flash(f'Le fichier {field.replace("_", " ")} doit être au format PDF, PNG ou JPG', 'error')
                    return redirect(url_for('formulaire_bourse'))
            
            db.session.add(new_request)
            db.session.flush()
            
            for field, file_key in files_required.items():
                file = request.files.get(file_key)
                if file and file.filename and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = secure_filename(f"{new_request.id}_{field}.{ext}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    setattr(new_request, field, filename)
            
            db.session.commit()
            
            try:
                send_confirmation_email_bourse(email, nom, prenom, new_request.id, categorie)
            except Exception as email_error:
                print(f"Erreur programmation email: {email_error}")
            
            flash('Votre demande de bourse a été soumise avec succès!', 'success')
            return redirect(url_for('information'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de la soumission: {str(e)}")
            flash('Une erreur est survenue. Veuillez réessayer.', 'error')
            return redirect(url_for('formulaire_bourse'))
    
    return render_template('form_bourse.html')

def send_confirmation_email_bourse(to_email, nom, prenom, request_id):
    """Envoyer un email de confirmation pour demande de bourse"""
    subject = "Confirmation de réception de votre demande de bourse"
    message = f"""Cher(e) {prenom} {nom},

Nous accusons réception de votre demande de bourse au sein du REED.

Votre dossier est en cours de traitement et vous serez notifié(e) par email dès qu'une décision sera prise.

Nous vous remercions pour votre confiance et n'oubliez pas de consulter vos emails section Spam.

Cordialement,
La Commission Sociale REED
"""
    
    try:
        thread = threading.Thread(
            target=send_email_async,
            args=(to_email, subject, message)
        )
        thread.daemon = True
        thread.start()
        print(f"✓ Email de confirmation bourse programmé pour {to_email}")
        
    except Exception as email_error:
        print(f"✗ Erreur d'envoi d'email: {email_error}")

@app.route('/admin/application_status', methods=['GET', 'POST'])
def admin_application_status():
    """Gérer l'ouverture/fermeture des demandes de logement et bourse"""
    if not session.get('admin_logged_in'):
        flash('Veuillez vous connecter', 'error')
        return redirect(url_for('admin_login'))
    
    app_status = ApplicationStatus.query.first()
    
    if request.method == 'POST':
        try:
            logement_open = request.form.get('logement_open') == 'on'
            bourse_open = request.form.get('bourse_open') == 'on'
            
            if not app_status:
                app_status = ApplicationStatus(
                    logement_open=logement_open,
                    bourse_open=bourse_open
                )
                db.session.add(app_status)
            else:
                app_status.logement_open = logement_open
                app_status.bourse_open = bourse_open
            
            db.session.commit()
            flash('Statut des demandes mis à jour avec succès', 'success')
            return redirect(url_for('admin_application_status'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'error')
    
    logement_count = StudentRequest.query.filter_by(request_type='logement').count()
    bourse_count = StudentRequest.query.filter_by(request_type='bourse').count()
    logement_pending = StudentRequest.query.filter_by(request_type='logement', status='pending').count()
    bourse_pending = StudentRequest.query.filter_by(request_type='bourse', status='pending').count()
    
    return render_template('admin_application_status.html', 
                         app_status=app_status,
                         logement_count=logement_count,
                         bourse_count=bourse_count,
                         logement_pending=logement_pending,
                         bourse_pending=bourse_pending)

# Gestion des erreurs
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"Erreur 500: {str(e)}")
    return render_template('500.html'), 500

# Initialisation
if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            # Créer le statut par défaut s'il n'existe pas
            if not ApplicationStatus.query.first():
                default_status = ApplicationStatus(logement_open=False, bourse_open=False)
                db.session.add(default_status)
                db.session.commit()
                print("✓ Statut par défaut créé (fermé)")
            print("✓ Base de données initialisée")
        except Exception as e:
            print(f"✗ Erreur initialisation DB: {str(e)}")
    
    print("\n" + "="*60)
    print("APPLICATION PRÊTE")
    print("="*60)
    print(f"Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Non configurée')[:50]}...")
    print(f"SendGrid: {'✓ Configuré' if app.config['SENDGRID_API_KEY'] else '✗ Non configuré'}")
    print(f"Sender: {app.config['MAIL_DEFAULT_SENDER']}")
    print("="*60 + "\n")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Upload folder exists: {os.path.exists(app.config['UPLOAD_FOLDER'])}")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)