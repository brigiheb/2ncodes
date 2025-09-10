# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies
from datetime import timedelta
from .. import db, socketio
from ..models.user import User
from werkzeug.utils import secure_filename
import os
from ..utils.socket_state import connected_users
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye
from datetime import datetime
from sqlalchemy import or_


users_bp = Blueprint('users', __name__, url_prefix='/users')

def save_user_photo(file, user_id):
    folder = os.path.join(current_app.root_path, 'static', 'users_photos')
    os.makedirs(folder, exist_ok=True)
    filename = f"{user_id}.png"
    save_path = os.path.join(folder, filename)

    if os.path.exists(save_path):
        os.remove(save_path)
    file.save(save_path)

    return os.path.relpath(save_path, current_app.root_path)

def emit_user_updated(user, exclude_user_id=None):
    """Helper function to emit user_updated event to relevant users."""
    user_data = {
        'id': user.id,
        'nom': user.nom,
        'email': user.email,
        'telephone': user.telephone,
        'niveau': user.niveau,
        'solde': float(user.solde),  # Ensure float for JSON serialization
        'role': user.role,
        'photo': user.photo,
        'etat': user.etat,
        'responsable': user.responsable
    }

    # Notify the user
    sid = connected_users.get(str(user.id))
    if sid:
        socketio.emit('user_updated', {'user_id': user.id, 'data': user_data}, room=sid)
        print(f"Emitted user_updated to user {user.id} with SID {sid}")

    # Notify the responsible admin (if applicable and not excluded)
    if user.responsable and user.responsable != exclude_user_id:
        sid = connected_users.get(str(user.responsable))
        if sid:
            socketio.emit('user_updated', {'user_id': user.id, 'data': user_data}, room=sid)
            print(f"Emitted user_updated to admin {user.responsable} with SID {sid}")

    # Notify all managers (except exclude_user_id)
    managers = User.query.filter(
    or_(
        User.role == 'manager',
        User.role == 'admin_boss'
    )).all()
    for manager in managers:
        if manager.id != exclude_user_id:
            sid = connected_users.get(str(manager.id))
            if sid:
                socketio.emit('user_updated', {'user_id': user.id, 'data': user_data}, room=sid)
                print(f"Emitted user_updated to manager {manager.id} with SID {sid}")

# ===================== SOCKET EVENTS ===================== #

@socketio.on('get_user_data')
def socket_get_user_data(data):
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    if not user:
        socketio.emit('user_data_error', {'error': 'User not found'}, room=request.sid)
        return

    user_data = {
        'id': user.id,
        'nom': user.nom,
        'email': user.email,
        'telephone': user.telephone,
        'niveau': user.niveau,
        'solde': float(user.solde),
        'role': user.role,
        'photo': user.photo,
        'etat': user.etat,
        'responsable': user.responsable
    }
    socketio.emit('user_data', {'user_id': user_id, 'data': user_data}, room=request.sid)


# ===================== ADD Admin_boss ===================== #

# Add near other imports if you want to validate privileges
import json

# Define allowed privileges
ALLOWED_ADMIN_BOSS_PRIVILEGES = [
    "acceder_articles", "ajouter_article", "modifier_article", "supprimer_article",
    "acceder_categories", "ajouter_categorie", "modifier_categorie", "supprimer_categorie",
    "acceder_sous_categories", "ajouter_sous_categorie", "modifier_sous_categorie", "supprimer_sous_categorie",
    "acceder_duree_sans_stock", "ajouter_duree_sans_stock", "modifier_duree_sans_stock", "supprimer_duree_sans_stock",
    "acceder_duree_avec_stock", "ajouter_duree_avec_stock", "modifier_duree_avec_stock", "supprimer_duree_avec_stock",
    "acceder_produits", "ajouter_produit", "modifier_produit", "supprimer_produit",
    "acceder_stock", "ajouter_stock", "modifier_stock", "supprimer_stock",
    "acceder_boutique_articles", "ajouter_boutique_article", "modifier_boutique_article", "supprimer_boutique_article",
    "acceder_boutique_categories", "ajouter_boutique_categorie", "modifier_boutique_categorie", "supprimer_boutique_categorie",
    "acceder_boutique_commandes", "modifier_boutique_commande", "supprimer_boutique_commande",
    "acceder_utilisateurs", "ajouter_utilisateur", "modifier_utilisateur", "supprimer_utilisateur",
    "acceder_admins", "ajouter_admin", "modifier_admin", "supprimer_admin",
    "acceder_revendeurs", "ajouter_revendeur", "modifier_revendeur", "supprimer_revendeur",
    "acceder_admins_produits", "ajouter_admin_produit", "modifier_admin_produit", "supprimer_admin_produit",
    "acceder_historiques", "performer_retour_commandes","imprimer_historique",
    "acceder_commandes", "modifier_commande", "supprimer_commande",
    "acceder_transactions_payees", "acceder_transactions_impayees","imprimer_transactions","voir_details_transaction",
    "acceder_applications", "ajouter_application", "modifier_application", "supprimer_application",
    "acceder_messages", "ajouter_message", "modifier_message", "supprimer_message",
    "acceder_demandes_solde", "repondre_demandes_solde"
]

@users_bp.route('/add_admin_boss', methods=['POST'])
@jwt_required()
def add_admin_boss():
    """
    Create an admin_boss user (only by a manager).
    Accepts multipart/form-data to support photo upload.
    Fields:
      - nom (required)
      - email (required)
      - telephone (required)
      - niveau (optional, default 'niveau1')
      - privileges (optional): JSON string OR comma-separated string
      - privilege (optional, repeatable): multiple form fields
      - photo (optional): file
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.role != "manager":
        return jsonify({"error": "Unauthorized. Only managers can create admin_boss users."}), 403

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    niveau = request.form.get('niveau', 'niveau1')  # Aligned with frontend default
    password = "123456"
    photo_file = request.files.get('photo')

    if not nom or not email or not telephone:
        return jsonify({"error": "nom, email, and telephone are required."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    # Parse privileges from form
    privileges = []
    # Option 1: repeated 'privilege' fields
    repeated = request.form.getlist('privilege')
    if repeated:
        privileges.extend([p.strip() for p in repeated if p.strip()])

    # Option 2: a single 'privileges' field (JSON string or comma-separated)
    raw_privs = request.form.get('privileges')
    if raw_privs:
        raw_privs = raw_privs.strip()
        parsed = []
        try:
            parsed = json.loads(raw_privs)
            if isinstance(parsed, str):
                parsed = [s.strip() for s in parsed.split(',') if s.strip()]
        except Exception:
            parsed = [s.strip() for s in raw_privs.split(',') if s.strip()]
        privileges.extend(parsed)

    # Deduplicate and validate privileges
    privileges = list({p for p in privileges if p})
    print("Received privileges:", privileges)  # Debug log
    print("Allowed privileges:", ALLOWED_ADMIN_BOSS_PRIVILEGES)  # Debug log
    invalid = [p for p in privileges if p not in ALLOWED_ADMIN_BOSS_PRIVILEGES]
    if invalid:
        return jsonify({
            "error": "Invalid privileges detected.",
            "invalid": invalid,
            "allowed": sorted(ALLOWED_ADMIN_BOSS_PRIVILEGES)
        }), 400

    new_admin_boss = User(
        nom=nom,
        email=email,
        telephone=telephone,
        niveau=niveau,
        solde=0,
        etat="actif",
        role="admin_boss",
        responsable=current_user.id,
        photo="default.png",
        admin_boss_privilege=privileges
    )
    new_admin_boss.set_password(password)
    db.session.add(new_admin_boss)
    db.session.flush()

    if photo_file and photo_file.filename:
        new_admin_boss.photo = save_user_photo(photo_file, new_admin_boss.id)

    db.session.commit()

    return jsonify(new_admin_boss.to_dict()), 201

# ===================== ADD USERS ===================== #

@users_bp.route('/add_manager', methods=['POST'])
def add_manager():
    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    solde = request.form.get('solde')
    password = "123456"
    photo_file = request.files.get('photo')

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    new_manager = User(
        nom=nom,
        email=email,
        telephone=telephone,
        niveau=None,
        solde=solde,
        etat="actif",
        role="manager",
        responsable=None,
        photo="default.png"
    )
    new_manager.set_password(password)
    db.session.add(new_manager)
    db.session.flush()

    if photo_file and photo_file.filename:
        new_manager.photo = save_user_photo(photo_file, new_manager.id)

    db.session.commit()
    return jsonify(new_manager.to_dict()), 201

@users_bp.route('/add_admin', methods=['POST'])
def add_admin():
    from ..routes.visible_items import assign_all_visible_items_to_user

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    niveau = request.form.get('niveau', 'niveau2')
    password = "123456"
    photo_file = request.files.get('photo')

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    new_admin = User(
        nom=nom,
        email=email,
        telephone=telephone,
        niveau=niveau,
        solde=0,
        etat="actif",
        role="admin",
        responsable=None,
        photo="default.png"
    )
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.flush()

    if photo_file and photo_file.filename:
        new_admin.photo = save_user_photo(photo_file, new_admin.id)

    db.session.commit()

    assign_all_visible_items_to_user(new_admin.id)

    return jsonify(new_admin.to_dict()), 201

@users_bp.route('/add_revendeur', methods=['POST'])
def add_revendeur():
    from ..routes.visible_items import assign_all_visible_items_to_user

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    admin_id = request.form.get('admin_id')
    niveau = request.form.get('niveau', 'niveau3')
    password = "123456"
    photo_file = request.files.get('photo')

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    admin = User.query.get(admin_id)
    if not admin or admin.role != 'admin':
        return jsonify({"error": "Admin not found or invalid role"}), 400

    new_revendeur = User(
        nom=nom,
        email=email,
        telephone=telephone,
        niveau=niveau,
        solde=0,
        etat="actif",
        role="revendeur",
        responsable=admin_id,
        photo="default.png"
    )
    new_revendeur.set_password(password)
    db.session.add(new_revendeur)
    db.session.flush()

    if photo_file and photo_file.filename:
        new_revendeur.photo = save_user_photo(photo_file, new_revendeur.id)

    db.session.commit()

    assign_all_visible_items_to_user(new_revendeur.id)

    return jsonify(new_revendeur.to_dict()), 201

# ===================== GET USERS ===================== #

@users_bp.route('/get_admins', methods=['GET'])
@jwt_required()
def get_admins():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if not current_user or current_user.role not in ["manager", "admin_boss"]:
        return jsonify({"error": "Unauthorized. Only managers or admin_boss can access this endpoint."}), 403

    search_query = request.args.get('search', '').strip().lower()
    page = request.args.get('page', type=int)
    per_page = request.args.get('per_page', type=int)

    # ✅ Filter depends on role
    if current_user.role == "manager":
        query = User.query.filter(User.role.in_(["admin", "admin_boss"]))
    else:  # admin_boss
        query = User.query.filter(User.role == "admin")

    if search_query:
        query = query.filter(
            db.or_(
                User.nom.ilike(f"%{search_query}%"),
                User.email.ilike(f"%{search_query}%"),
                User.telephone.ilike(f"%{search_query}%")
            )
        )

    if page is None and per_page is None:
        admins = query.order_by(User.id.desc()).all()
        return jsonify({
            "page": 1,
            "per_page": len(admins),
            "total": len(admins),
            "pages": 1,
            "admins": [{
                "id": admin.id,
                "photo": admin.photo,
                "nom": admin.nom,
                "email": admin.email,
                "telephone": admin.telephone,
                "niveau": admin.niveau,
                "role": admin.role,
                "etat": admin.etat,
                "solde": float(admin.solde)
            } for admin in admins]
        }), 200

    per_page = per_page or 20
    page = page or 1
    paginated = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    admins = paginated.items

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "admins": [{
            "id": admin.id,
            "photo": admin.photo,
            "nom": admin.nom,
            "email": admin.email,
            "telephone": admin.telephone,
            "niveau": admin.niveau,
            "role": admin.role,
            "etat": admin.etat,
            "solde": float(admin.solde),
            "admin_boss_privilege": getattr(admin, "admin_boss_privilege", None)
        } for admin in admins]
    }), 200

@users_bp.route('/get_revendeurs', methods=['GET'])
@jwt_required()
def get_revendeurs():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    if current_user.role not in ["manager", "admin", "admin_boss"]:
        return jsonify({"error": "Unauthorized. Only managers and admins can access this endpoint."}), 403

    search_query = request.args.get('search', '').strip().lower()
    page = request.args.get('page', type=int, default=1)
    per_page = 20

    if current_user.role in ["manager","admin_boss"]:
        query = User.query.filter_by(role="revendeur")
    else:
        def get_sub_revendeur_ids(admin_id):
            revendeur_ids = []
            direct_revendeurs = User.query.filter_by(responsable=admin_id, role="revendeur").all()
            revendeur_ids += [r.id for r in direct_revendeurs]
            sub_admins = User.query.filter_by(responsable=admin_id, role="admin").all()
            for sub_admin in sub_admins:
                revendeur_ids += get_sub_revendeur_ids(sub_admin.id)
            return revendeur_ids

        ids = get_sub_revendeur_ids(current_user.id)
        query = User.query.filter(User.id.in_(ids))

    if search_query:
        query = query.filter(
            db.or_(
                User.nom.ilike(f"%{search_query}%"),
                User.email.ilike(f"%{search_query}%"),
                User.telephone.ilike(f"%{search_query}%")
            )
        )

    paginated = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    revendeurs = paginated.items

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "revendeurs": [{
            "id": r.id,
            "photo": r.photo,
            "admin": User.query.get(r.responsable).nom if r.responsable else None,
            "nom": r.nom,
            "email": r.email,
            "telephone": r.telephone,
            "niveau": r.niveau,
            "role": r.role,
            "etat": r.etat,
            "solde": float(r.solde)
        } for r in revendeurs]
    }), 200

# ===================== UPDATE USERS ===================== #

@users_bp.route('/update_manager/<int:manager_id>', methods=['PUT'])
@jwt_required()
def update_manager(manager_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.role != "manager" or current_user.id != manager_id:
        return jsonify({"error": "Unauthorized. Only managers can update their own profile."}), 403

    manager = User.query.get(manager_id)
    if not manager or manager.role != 'manager':
        return jsonify({"error": "Manager not found or invalid role"}), 404

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    password = request.form.get('password')
    photo_file = request.files.get('photo')

    if email and email != manager.email and User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400

    if telephone and telephone != manager.telephone and User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    manager.nom = nom or manager.nom
    manager.email = email or manager.email
    manager.telephone = telephone or manager.telephone

    if password:
        manager.set_password(password)

    if photo_file and photo_file.filename:
        manager.photo = save_user_photo(photo_file, manager.id)

    db.session.commit()
    emit_user_updated(manager, exclude_user_id=current_user.id)
    return jsonify(manager.to_dict()), 200

@users_bp.route('/update_admin/<int:admin_id>', methods=['PUT'])
@jwt_required()
def update_admin(admin_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.role not in ["manager","admin_boss"]:
        return jsonify({"error": "Unauthorized. Only managers can update admins."}), 403

    admin = User.query.get(admin_id)

    if not admin or admin.role not in ['admin', 'admin_boss']:
        return jsonify({"error": "Admin not found or invalid role"}), 404

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    etat = request.form.get('etat')
    niveau = request.form.get('niveau')
    solde = request.form.get('solde')
    password = request.form.get('password')
    photo_file = request.files.get('photo')

    if email and email != admin.email and User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400

    if telephone and telephone != admin.telephone and User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    admin.nom = nom or admin.nom
    admin.email = email or admin.email
    admin.telephone = telephone or admin.telephone
    admin.etat = etat or admin.etat
    admin.niveau = niveau or admin.niveau
    admin.solde = float(solde) if solde else admin.solde

    if password:
        admin.set_password(password)

    if photo_file and photo_file.filename:
        admin.photo = save_user_photo(photo_file, admin.id)

    db.session.commit()
    emit_user_updated(admin, exclude_user_id=current_user.id)
    return jsonify(admin.to_dict()), 200


@users_bp.route('/update_admin_boss/<int:id>', methods=['PUT'])
@jwt_required()
def update_admin_boss(id):
    """
    Update an admin_boss user (only by a manager).
    Accepts multipart/form-data to support photo upload.
    Fields:
      - nom (optional)
      - email (optional)
      - telephone (optional)
      - niveau (optional)
      - privileges (optional): JSON string OR comma-separated string
      - privilege (optional, repeatable): multiple form fields
      - photo (optional): file
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.role != "manager":
        return jsonify({"error": "Unauthorized. Only managers can update admin_boss users."}), 403

    admin_boss = User.query.get(id)
    if not admin_boss or admin_boss.role != "admin_boss":
        return jsonify({"error": "Admin boss not found or invalid role."}), 404

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    niveau = request.form.get('niveau')
    photo_file = request.files.get('photo')

    # Validate email and telephone if provided
    if email and email != admin_boss.email and User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if telephone and telephone != admin_boss.telephone and User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    # Update fields if provided
    if nom:
        admin_boss.nom = nom
    if email:
        admin_boss.email = email
    if telephone:
        admin_boss.telephone = telephone
    if niveau:
        admin_boss.niveau = niveau

    # Parse privileges from form
    privileges = []
    # Option 1: repeated 'privilege' fields
    repeated = request.form.getlist('privilege')
    if repeated:
        privileges.extend([p.strip() for p in repeated if p.strip()])

    # Option 2: a single 'privileges' field (JSON string or comma-separated)
    raw_privs = request.form.get('privileges')
    if raw_privs:
        raw_privs = raw_privs.strip()
        parsed = []
        try:
            parsed = json.loads(raw_privs)
            if isinstance(parsed, str):
                parsed = [s.strip() for s in parsed.split(',') if s.strip()]
        except Exception:
            parsed = [s.strip() for s in raw_privs.split(',') if s.strip()]
        privileges.extend(parsed)

    # Deduplicate and validate privileges
    if privileges:
        privileges = list({p for p in privileges if p})
        print("Received privileges:", privileges)  # Debug log
        print("Allowed privileges:", ALLOWED_ADMIN_BOSS_PRIVILEGES)  # Debug log
        invalid = [p for p in privileges if p not in ALLOWED_ADMIN_BOSS_PRIVILEGES]
        if invalid:
            return jsonify({
                "error": "Invalid privileges detected.",
                "invalid": invalid,
                "allowed": sorted(ALLOWED_ADMIN_BOSS_PRIVILEGES)
            }), 400
        admin_boss.admin_boss_privilege = privileges

    if photo_file and photo_file.filename:
        admin_boss.photo = save_user_photo(photo_file, admin_boss.id)

    db.session.commit()
    return jsonify(admin_boss.to_dict()), 200

@users_bp.route('/update_revendeur/<int:revendeur_id>', methods=['PUT'])
@jwt_required()
def update_revendeur(revendeur_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.role not in ["manager", "admin"]:
        return jsonify({"error": "Unauthorized. Only managers and admins can update revendeurs."}), 403

    revendeur = User.query.get(revendeur_id)
    if not revendeur or revendeur.role != 'revendeur':
        return jsonify({"error": "Revendeur not found or invalid role"}), 404

    if current_user.role == "admin" and revendeur.responsable != current_user.id:
        return jsonify({"error": "Admins can only update their own revendeurs."}), 403

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    etat = request.form.get('etat')
    niveau = request.form.get('niveau')
    solde = request.form.get('solde')
    admin_id = request.form.get('admin_id')
    password = request.form.get('password')
    photo_file = request.files.get('photo')

    if email and email != revendeur.email and User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400

    if telephone and telephone != revendeur.telephone and User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    revendeur.nom = nom or revendeur.nom
    revendeur.email = email or revendeur.email
    revendeur.telephone = telephone or revendeur.telephone
    revendeur.etat = etat or revendeur.etat
    revendeur.niveau = niveau or revendeur.niveau
    revendeur.solde = float(solde) if solde else revendeur.solde

    if password:
        revendeur.set_password(password)

    if admin_id:
        admin = User.query.get(admin_id)
        if not admin or admin.role != 'admin':
            return jsonify({"error": "Admin not found or invalid role"}), 400
        revendeur.responsable = admin_id

    if photo_file and photo_file.filename:
        revendeur.photo = save_user_photo(photo_file, revendeur.id)

    db.session.commit()
    emit_user_updated(revendeur, exclude_user_id=current_user.id)
    return jsonify(revendeur.to_dict()), 200

# ===================== LOGIN & LOGOUT ===================== #

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 404

    access_token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=1))
    return jsonify({
        "message": "Login successful",
        "token": access_token,
        "role": user.role,
        "user_id": user.id,
        "nom": user.nom,
        "email": user.email,
        "email": user.email,
        "admin_boss_privilege": user.admin_boss_privilege,
    }), 200

@users_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    response = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(response)
    return response, 200

# ===================== UPDATE SOLDE ===================== #

@users_bp.route('/update_solde/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_solde(user_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return jsonify({"error": "Utilisateur non autorisé. Utilisateur non trouvé."}), 403

    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "Utilisateur non trouvé."}), 404

    data = request.get_json()
    montant = data.get('montant')
    etat = data.get('etat', 'impaye')
    duree = data.get('duree')

    if not isinstance(montant, (int, float)):
        return jsonify({"error": "Montant invalide. Il doit être un nombre."}), 400

    if etat not in ["paye", "impaye"]:
        return jsonify({"error": "L'état doit être 'paye' ou 'impaye'."}), 400

    if etat == "impaye" and (not duree or duree not in ["1 jour", "3 jours", "7 jours", "14 jours", "1 mois", "2 mois", "3 mois"]):
        return jsonify({"error": "Durée invalide ou manquante pour une transaction impayée."}), 400

    if current_user.role in ["manager", "admin_boss"]:
        new_solde = target_user.solde + montant
        if new_solde < 0:
            return jsonify({"error": "Solde insuffisant."}), 400
        target_user.solde = new_solde

    elif current_user.role == "admin":
        if target_user.role != "revendeur" or target_user.responsable != current_user.id:
            return jsonify({"error": "Les administrateurs ne peuvent gérer que leurs propres revendeurs."}), 403
        if montant < 0:
            return jsonify({"error": "Les administrateurs ne peuvent qu'ajouter du solde, pas en retirer."}), 400
        # Deduct from admin's solde
        if current_user.solde < montant:
            return jsonify({"error": "Solde insuffisant pour l'administrateur."}), 400
        current_user.solde -= montant
        target_user.solde += montant

    else:
        return jsonify({"error": "Rôle non autorisé."}), 403

    if etat == "paye":
        transaction = TransactionPaye(
            envoyee_par=current_user.id,
            recue_par=target_user.id,
            montant=montant,
            preuve="manual_update.png",
            date_transaction=datetime.utcnow(),
            etat="paye"
        )
    else:
        transaction = TransactionImpaye(
            envoyee_par=current_user.id,
            recue_par=target_user.id,
            montant=montant,
            date_transaction=datetime.utcnow(),
            etat="impaye",
            duree=duree
        )
    db.session.add(transaction)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Échec de la validation de la base de données pour l'utilisateur {user_id}: {str(e)}")
        return jsonify({"error": "Erreur de base de données."}), 500

    emit_user_updated(target_user, exclude_user_id=current_user.id)
    if current_user.role == "admin":
        emit_user_updated(current_user, exclude_user_id=current_user.id)  # Emit for admin
    return jsonify({
        "message": "Solde mis à jour avec succès",
        "user_id": target_user.id,
        "role": target_user.role,
        "solde": float(target_user.solde),
        "etat": etat,
        "duree": duree if etat == "impaye" else None
    }), 200
# ===================== SWITCH REVENDEUR RESPONSABLE ===================== #

@users_bp.route('/switch_revendeur', methods=['PUT'])
@jwt_required()
def switch_revendeur_responsable():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.role not in ("manager", "admin_boss"):
        return jsonify({"error": "Unauthorized. Only managers can switch revendeurs."}), 403

    data = request.get_json()
    revendeur_id = data.get('revendeur_id')
    new_admin_id = data.get('new_admin_id')

    revendeur = User.query.get(revendeur_id)
    new_admin = User.query.get(new_admin_id)

    if not revendeur or revendeur.role != 'revendeur':
        return jsonify({"error": "Revendeur not found or invalid role."}), 404

    if not new_admin or new_admin.role != 'admin':
        return jsonify({"error": "New admin not found or invalid role."}), 404

    revendeur.responsable = new_admin_id
    db.session.commit()

    emit_user_updated(revendeur, exclude_user_id=current_user.id)
    return jsonify({
        "message": f"Revendeur {revendeur.nom} is now assigned to Admin {new_admin.nom}.",
        "revendeur_id": revendeur.id,
        "new_admin_id": new_admin.id
    }), 200

# ===================== GET USER AFTER LOGIN ===================== #

@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "photo": user.photo,
        "nom": user.nom,
        "email": user.email,
        "telephone": user.telephone,
        "niveau": user.niveau,
        "role": user.role,
        "solde": float(user.solde),
        "admin_boss_privilege": user.admin_boss_privilege,
    }), 200

# ===================== UPDATE PASSWORD ===================== #

@users_bp.route('/change_password', methods=['PUT'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({"error": "Both old and new passwords are required"}), 400

    if not user.check_password(old_password):
        return jsonify({"error": "Old password is incorrect"}), 404

    user.set_password(new_password)
    db.session.commit()

    emit_user_updated(user, exclude_user_id=user_id)
    return jsonify({"message": "Password updated successfully"}), 200

@users_bp.route('/reset_password/<int:user_id>', methods=['PUT'])
@jwt_required()
def reset_password(user_id):
    manager_id = get_jwt_identity()
    manager = User.query.get(manager_id)
    if not manager or manager.role not in ("manager", "admin_boss"):
        return jsonify({"error": "Unauthorized access"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role not in ["admin", "revendeur"]:
        return jsonify({"error": "You can only reset passwords for admins or revendeurs"}), 403

    default_password = "123456"
    user.set_password(default_password)
    db.session.commit()

    emit_user_updated(user, exclude_user_id=manager_id)
    access_token = create_access_token(identity=user.id)
    return jsonify({
        "message": f"Password for {user.nom} has been reset to default.",
        "new_password": default_password,
        "access_token": access_token
    }), 200

@users_bp.route('/connected', methods=['GET'])
@jwt_required()
def get_connected_users():
    ids = list(connected_users.keys())
    users = User.query.filter(User.id.in_(ids)).all()
    return jsonify([
        {
            "id": user.id,
            "nom": user.nom,
            "email": user.email,
            "role": user.role,
            "photo": user.photo
        }
        for user in users
    ]), 200