# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies
from datetime import timedelta
from .. import db
from ..models.user import User
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

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

# ===================== ADD USERS ===================== #

@users_bp.route('/add_manager', methods=['POST'])
def add_manager():
    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    password = "123456"
    photo_file = request.files.get('photo')

    # Check for existing email or telephone
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400
    new_manager = User(
        nom=nom,
        email=email,
        telephone=telephone,
        niveau=None,
        solde=0.0,
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
    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    niveau = request.form.get('niveau', 'niveau2')
    password = "123456"
    photo_file = request.files.get('photo')

    # Check for existing email or telephone
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    if User.query.filter_by(telephone=telephone).first():
        return jsonify({"error": "Telephone already exists"}), 400

    new_admin = User(
        nom=nom,
        email=email,
        telephone=telephone,
        niveau=niveau,
        solde=0.0,
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
    return jsonify(new_admin.to_dict()), 201


@users_bp.route('/add_revendeur', methods=['POST'])
def add_revendeur():
    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    admin_id = request.form.get('admin_id')
    niveau = request.form.get('niveau', 'niveau3')
    password = "123456"
    photo_file = request.files.get('photo')

    # Check for existing email or telephone
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
        solde=0.0,
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
    return jsonify(new_revendeur.to_dict()), 201


# ===================== GET USERS ===================== #

@users_bp.route('/get_admins', methods=['GET'])
def get_admins():
    """Get all admins."""
    admins = User.query.filter_by(role="admin").all()
    return jsonify([{
        "id": admin.id,
        "photo": admin.photo,
        "nom": admin.nom,
        "email": admin.email,
        "telephone": admin.telephone,
        "niveau": admin.niveau,
        "role": admin.role,
        "etat": admin.etat,
        "solde": admin.solde  # ✅ Added solde
    } for admin in admins]), 200


@users_bp.route('/get_revendeurs', methods=['GET'])
def get_revendeurs():
    """Get all revendeurs with admin info."""
    revendeurs = User.query.filter_by(role="revendeur").all()
    return jsonify([{
        "id": revendeur.id,
        "photo": revendeur.photo,
        "admin": User.query.get(revendeur.responsable).nom if revendeur.responsable else None,
        "nom": revendeur.nom,
        "email": revendeur.email,
        "telephone": revendeur.telephone,
        "role": revendeur.role,
        "etat": revendeur.etat,
        "solde": revendeur.solde  # ✅ Added solde
    } for revendeur in revendeurs]), 200



# ===================== UPDATE USERS ===================== #

@users_bp.route('/update_admin/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    admin = User.query.get(admin_id)
    if not admin or admin.role != 'admin':
        return jsonify({"error": "Admin not found or invalid role"}), 404

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    etat = request.form.get('etat')
    niveau = request.form.get('niveau')
    solde = request.form.get('solde')
    password = request.form.get('password')
    photo_file = request.files.get('photo')

    # 🔒 Check for duplicate email
    if email and email != admin.email:
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 400

    # 🔒 Check for duplicate telephone
    if telephone and telephone != admin.telephone:
        if User.query.filter_by(telephone=telephone).first():
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
    return jsonify(admin.to_dict()), 200


@users_bp.route('/update_revendeur/<int:revendeur_id>', methods=['PUT'])
def update_revendeur(revendeur_id):
    revendeur = User.query.get(revendeur_id)
    if not revendeur or revendeur.role != 'revendeur':
        return jsonify({"error": "Revendeur not found or invalid role"}), 404

    nom = request.form.get('nom')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    etat = request.form.get('etat')
    niveau = request.form.get('niveau')
    solde = request.form.get('solde')
    admin_id = request.form.get('admin_id')
    password = request.form.get('password')
    photo_file = request.files.get('photo')

    # 🔒 Check for duplicate email
    if email and email != revendeur.email:
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 400

    # 🔒 Check for duplicate telephone
    if telephone and telephone != revendeur.telephone:
        if User.query.filter_by(telephone=telephone).first():
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
    return jsonify(revendeur.to_dict()), 200


# ===================== LOGIN & LOGOUT ===================== #

@users_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    access_token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=24))

    return jsonify({
        "message": "Login successful ?",
        "token": access_token,
        "role": user.role,
        "user_id": user.id,
        "nom": user.nom,
        "email": user.email
    }), 200


@users_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout endpoint."""
    response = jsonify({"message": "Logout successful ✅"})
    unset_jwt_cookies(response)
    return response, 200



# ===================== Update Solde ===================== #
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye
from datetime import datetime

@users_bp.route('/update_solde/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_solde(user_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return jsonify({"error": "Unauthorized. User not found."}), 403

    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()
    montant = data.get('montant')
    etat = data.get('etat', 'impaye')  # default to impaye if not provided

    if not isinstance(montant, (int, float)):
        return jsonify({"error": "Invalid montant. It must be a number."}), 400

    if etat not in ["paye", "impaye"]:
        return jsonify({"error": "Etat must be 'paye' or 'impaye'."}), 400

    if current_user.role == "manager":
        new_solde = target_user.solde + montant
        if new_solde < 0:
            return jsonify({"error": "Insufficient solde."}), 400
        target_user.solde = new_solde

    elif current_user.role == "admin":
        if target_user.role != "revendeur" or target_user.responsable != current_user.id:
            return jsonify({"error": "Admins can only manage their own Revendeurs."}), 403
        if montant < 0:
            return jsonify({"error": "Admins can only increase solde."}), 403
        target_user.solde += montant

    else:
        return jsonify({"error": "Unauthorized role."}), 403

    # ✅ Save transaction
    if etat == "paye":
        transaction = TransactionPaye(
            envoyee_par=current_user.id,
            recue_par=target_user.id,
            montant=montant,
            preuve="manual_update.png",  # placeholder
            date_transaction=datetime.utcnow(),
            etat="paye"
        )
    else:
        transaction = TransactionImpaye(
            envoyee_par=current_user.id,
            recue_par=target_user.id,
            montant=montant,
            date_transaction=datetime.utcnow(),
            etat="impaye"
        )
    db.session.add(transaction)

    db.session.commit()
    return jsonify({
        "message": "Solde updated successfully",
        "user_id": target_user.id,
        "role": target_user.role,
        "new_solde": target_user.solde,
        "etat": etat
    }), 200

# ===================== SWITCH REVENDEUR RESPONSABLE ===================== #
@users_bp.route('/switch_revendeur', methods=['PUT'])
@jwt_required()
def switch_revendeur_responsable():
    """Manager can switch a Revendeur from Admin X to Admin Y."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if not current_user or current_user.role != "manager":
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

    # Switch the revendeur's responsable
    revendeur.responsable = new_admin_id
    db.session.commit()

    return jsonify({
        "message": f"Revendeur {revendeur.nom} is now assigned to Admin {new_admin.nom}. ✅",
        "revendeur_id": revendeur.id,
        "new_admin_id": new_admin.id
    }), 200

# ===================== GET USER AFTER LOGIN ===================== #

@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get the details of the currently logged-in user."""
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
        "solde": user.solde
    }), 200
# ===================== UPDATE PASSWORD ===================== #
@users_bp.route('/change_password', methods=['PUT'])
@jwt_required()
def change_password():
    """Allow logged-in users to change their password."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({"error": "Both old and new passwords are required"}), 400

    # ✅ Use the model's `check_password` method
    if not user.check_password(old_password):
        return jsonify({"error": "Old password is incorrect"}), 401

    # ✅ Use the `set_password` method to update the password
    user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Password updated successfully"}), 200



@users_bp.route('/reset_password/<int:user_id>', methods=['PUT'])
@jwt_required()
def reset_password(user_id):
    """Allow managers to reset the password of an admin or revendeur."""
    manager_id = get_jwt_identity()
    manager = User.query.get(manager_id)

    if not manager or manager.role != "manager":
        return jsonify({"error": "Unauthorized access"}), 403

    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role not in ["admin", "revendeur"]:
        return jsonify({"error": "You can only reset passwords for admins or revendeurs"}), 403

    # ✅ Set the new default password to "123456"
    default_password = "123456"
    user.set_password(default_password)

    db.session.commit()

    # ✅ Automatically generate a new login token for the user
    access_token = create_access_token(identity=user.id)

    return jsonify({
        "message": f"Password for {user.nom} has been reset to default.",
        "new_password": default_password,
        "access_token": access_token
    }), 200
