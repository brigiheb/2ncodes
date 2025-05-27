# -*- coding: utf-8 -*-
import os
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models.user import User
from ..models.demande_solde import DemandeSolde
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye
from datetime import datetime
from app import socketio  # ✅ Socket import

demande_solde_bp = Blueprint('demande_solde', __name__, url_prefix='/demande_solde')

# Track connected users
connected_users = {}

@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('userId')
    if user_id:
        connected_users[user_id] = request.sid
    print(f"User {user_id} connected with SID: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    user_id = next((k for k, v in connected_users.items() if v == request.sid), None)
    if user_id:
        del connected_users[user_id]
    print(f"User {user_id} disconnected")


# ✅ 1. Submit a Demande Solde
@demande_solde_bp.route('/add', methods=['POST'])
@jwt_required()
def create_demande_solde():
    montant = request.form.get('montant', type=float)
    photo_file = request.files.get('preuve')

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role == "revendeur" and (montant is None or montant < 150.0):
        return jsonify({"error": "Revendeurs must request at least 150.0"}), 400

    new_request = DemandeSolde(envoyee_par=user.id, montant=montant)
    db.session.add(new_request)
    db.session.flush()

    if photo_file and photo_file.filename:
        folder = os.path.join(current_app.root_path, 'static', 'demande_solde', 'preuves')
        os.makedirs(folder, exist_ok=True)
        filename = f"{new_request.id}.png"
        save_path = os.path.join(folder, filename)
        photo_file.save(save_path)
        new_request.preuve = os.path.relpath(save_path, current_app.root_path)

    db.session.commit()

    # Enhanced emit with proper room targeting
    managers = User.query.filter_by(role='manager').all()
    for manager in managers:
        if str(manager.id) in connected_users:
            socketio.emit('new_demande_solde', {
                "id": new_request.id,
                "montant": montant,
                "envoyee_par": user.nom,
                "role": user.role,
                "user_id": user.id
            }, room=connected_users[str(manager.id)])

    return jsonify(new_request.to_dict()), 201


# ✅ 2. Get Demandes by Role
@demande_solde_bp.route('/get', methods=['GET'])
@jwt_required()
def get_all_demandes():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role == "manager":
        demandes = (
            DemandeSolde.query
            .join(User)
            .filter(User.role == "admin")
            .order_by(DemandeSolde.date_demande.desc())
            .all()
        )
    elif user.role == "admin":
        demandes = (
            DemandeSolde.query
            .join(User)
            .filter(User.responsable == user.id)
            .order_by(DemandeSolde.date_demande.desc())
            .all()
        )
    else:
        return jsonify({"error": "Unauthorized access"}), 403

    return jsonify([
        {
            **demande.to_dict(),
            "user_id": demande.user.id
        }
        for demande in demandes
    ]), 200


# ✅ 3. Approve or Reject a Demande Solde
@demande_solde_bp.route('/update/<int:demande_id>', methods=['PUT'])
@jwt_required()
def update_demande(demande_id):
    data = request.get_json()
    etat = data.get('etat')

    if etat not in ["confirmé", "annulé"]:
        return jsonify({"error": "Invalid state"}), 400

    user_id = get_jwt_identity()
    approver = User.query.get(user_id)
    if not approver:
        return jsonify({"error": "User not found"}), 404

    demande = DemandeSolde.query.get(demande_id)
    if not demande:
        return jsonify({"error": "Demande not found"}), 404

    requester = User.query.get(demande.envoyee_par)
    if not requester:
        return jsonify({"error": "Requester not found"}), 404

    if approver.role == "manager" and requester.role == "admin":
        pass
    elif approver.role == "admin" and requester.role == "revendeur":
        if etat == "confirmé" and demande.montant > approver.solde:
            return jsonify({"error": "Insufficient solde to approve this request."}), 400
    else:
        return jsonify({"error": "Unauthorized action"}), 403

    demande.etat = etat

    if etat == "confirmé":
        # 🔁 Solde transfer logic
        if approver.role == "admin" and requester.role == "revendeur":
            approver.solde -= demande.montant
            requester.solde += demande.montant
        elif approver.role == "manager" and requester.role == "admin":
            requester.solde += demande.montant

        # ✅ Log transaction
        transaction_data = {
            "envoyee_par": approver.id,
            "recue_par": requester.id,
            "montant": demande.montant,
            "date_transaction": demande.date_demande,
            "date_paiement": datetime.utcnow()
        }

        if demande.preuve:
            transaction = TransactionPaye(
                preuve=demande.preuve,
                etat="paye",
                **transaction_data
            )
        else:
            transaction = TransactionImpaye(
                etat="impaye",
                **transaction_data
            )

        db.session.add(transaction)

        # ✅ Emit socket event for confirmation
        socketio.emit('demande_confirmee', {
            "id": demande.id,
            "montant": demande.montant,
            "from": approver.nom,
            "to": requester.nom,
            "etat": "confirmé"
        })

    elif etat == "annulé":
        # ✅ Emit socket event for cancellation
        socketio.emit('demande_annulee', {
            "id": demande.id,
            "montant": demande.montant,
            "from": approver.nom,
            "to": requester.nom,
            "etat": "annulé"
        })

    db.session.commit()
    return jsonify({
        "message": f"Demande {etat} successfully",
        "updated_demande": demande.to_dict()
    }), 200
