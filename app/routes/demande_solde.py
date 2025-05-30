# -*- coding: utf-8 -*-
import os
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models.user import User
from ..models.demande_solde import DemandeSolde
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye
from datetime import datetime, timedelta
from app import socketio

from app.utils.socket_state import connected_users

demande_solde_bp = Blueprint('demande_solde', __name__, url_prefix='/demande_solde')

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

# ✅ New Socket: Real-time en cours count
@socketio.on("get_en_cours_count")
def socket_get_en_cours_count(data):
    user_id = data.get("user_id")
    user = User.query.get(user_id)
    if user:
        count = get_en_cours_count(user)
        socketio.emit("en_cours_count", {"user_id": user_id, "count": count}, room=request.sid)

# ✅ New Socket: Weekly confirmed/annulled demandes
@socketio.on("get_weekly_confirmed_and_cancelled")
def socket_get_weekly_updates(data):
    user_id = data.get("user_id")
    user = User.query.get(user_id)
    if not user:
        return

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    demandes = []

    if user.role == "manager":
        demandes = DemandeSolde.query.join(User).filter(
            User.role == "admin",
            DemandeSolde.date_demande >= one_week_ago,
            DemandeSolde.etat.in_(["confirmé", "annulé"])
        ).all()
    elif user.role == "admin":
        demandes = DemandeSolde.query.join(User).filter(
            User.role == "revendeur",
            User.responsable == user.id,
            DemandeSolde.date_demande >= one_week_ago,
            DemandeSolde.etat.in_(["confirmé", "annulé"])
        ).all()

    confirmed = [d.to_dict() for d in demandes if d.etat == "confirmé"]
    cancelled = [d.to_dict() for d in demandes if d.etat == "annulé"]

    socketio.emit("weekly_confirmed_and_cancelled", {
        "user_id": user_id,
        "confirmed": confirmed,
        "cancelled": cancelled
    }, room=request.sid)

# 🔧 Utility to get en cours count
def get_en_cours_count(user):
    if user.role == "manager":
        return DemandeSolde.query.join(User).filter(
            User.role == "admin",
            DemandeSolde.etat == "en cours"
        ).count()
    elif user.role == "admin":
        return DemandeSolde.query.join(User).filter(
            User.role == "revendeur",
            User.responsable == user.id,
            DemandeSolde.etat == "en cours"
        ).count()
    return 0

# ✅ 1. Submit Demande
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

    managers = User.query.filter_by(role='manager').all()
    for manager in managers:
        sid = connected_users.get(str(manager.id))
        if sid:
            socketio.emit('new_demande_solde', {
                "id": new_request.id,
                "montant": montant,
                "envoyee_par": user.nom,
                "role": user.role,
                "user_id": user.id
            }, room=sid)

            count = get_en_cours_count(manager)
            socketio.emit("update_en_cours_count", {
                "user_id": manager.id,
                "count": count
            }, room=sid)

    return jsonify(new_request.to_dict()), 201

# ✅ 2. Get Demandes
@demande_solde_bp.route('/get', methods=['GET'])
@jwt_required()
def get_all_demandes():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role == "manager":
        demandes = DemandeSolde.query.join(User).filter(
            User.role == "admin"
        ).order_by(DemandeSolde.date_demande.desc()).all()
    elif user.role == "admin":
        demandes = DemandeSolde.query.join(User).filter(
            User.responsable == user.id
        ).order_by(DemandeSolde.date_demande.desc()).all()
    else:
        return jsonify({"error": "Unauthorized access"}), 403

    return jsonify([
        {
            **demande.to_dict(),
            "user_id": demande.user.id
        }
        for demande in demandes
    ]), 200

# ✅ Utility
def validate_etat(etat):
    if etat not in ["confirmé", "annulé"]:
        return False, jsonify({"error": "Invalid state"}), 400
    return True, None, None

def verify_roles(approver, requester, etat, montant):
    if approver.role == "manager" and requester.role == "admin":
        return True, None
    elif approver.role == "admin" and requester.role == "revendeur":
        if etat == "confirmé" and montant > approver.solde:
            return False, jsonify({"error": "Insufficient solde"}), 400
        return True, None
    return False, jsonify({"error": "Unauthorized"}), 403

# ✅ 3. Update Demande
@demande_solde_bp.route('/update/<int:demande_id>', methods=['PUT'])
@jwt_required()
def update_demande(demande_id):
    data = request.get_json()
    etat = data.get('etat')

    valid, error_response, status_code = validate_etat(etat)
    if not valid:
        return error_response, status_code

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

    authorized, error_response = verify_roles(approver, requester, etat, demande.montant)
    if not authorized:
        return error_response

    demande.etat = etat

    if etat == "confirmé":
        if approver.role == "admin" and requester.role == "revendeur":
            approver.solde -= demande.montant
            requester.solde += demande.montant
        elif approver.role == "manager" and requester.role == "admin":
            requester.solde += demande.montant

        tx_data = {
            "envoyee_par": approver.id,
            "recue_par": requester.id,
            "montant": demande.montant,
            "date_transaction": demande.date_demande
        }

        tx = (
            TransactionPaye(preuve=demande.preuve, etat="paye", **tx_data)
            if demande.preuve else
            TransactionImpaye(etat="impaye", **tx_data)
        )
        db.session.add(tx)

    db.session.commit()

    sid = connected_users.get(str(requester.id))
    if sid:
        socketio.emit(f"demande_{etat}", {
            "id": demande.id,
            "montant": demande.montant,
            "from": approver.nom,
            "to": requester.nom,
            "etat": etat
        }, room=sid)

        count = get_en_cours_count(requester)
        socketio.emit("update_en_cours_count", {
            "user_id": requester.id,
            "count": count
        }, room=sid)

    return jsonify({
        "message": f"Demande {etat} successfully",
        "updated_demande": demande.to_dict()
    }), 200