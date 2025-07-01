# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db, socketio
from app.models.user import User
from app.models.demande_solde import DemandeSolde
from app.models.transaction_paye import TransactionPaye
from app.models.transaction_impaye import TransactionImpaye
from app.utils.socket_state import connected_users

demande_solde_bp = Blueprint('demande_solde', __name__, url_prefix='/demande_solde')

@socketio.on('connect')
def handle_connect():
    try:
        user_id = request.args.get('userId')
    except Exception:
        user_id = None

    if user_id:
        connected_users[user_id] = request.sid
        print(f"User {user_id} connected with SID: {request.sid}")
    else:
        print(f"Unknown user connected with SID: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    user_id = next((k for k, v in connected_users.items() if v == request.sid), None)
    if user_id:
        del connected_users[user_id]
        print(f"User {user_id} disconnected")

@socketio.on("get_en_cours_count")
def socket_get_en_cours_count(data):
    user_id = data.get("user_id")
    user = User.query.get(user_id)
    if user:
        count = get_en_cours_count(user)
        socketio.emit("en_cours_count", {"user_id": user_id, "count": count}, room=request.sid)

@socketio.on("get_weekly_confirmed_and_cancelled")
def socket_get_weekly_updates(data):
    user_id = data.get("user_id")
    user = User.query.get(user_id)
    if not user:
        print(f"User {user_id} not found for weekly_confirmed_and_cancelled")
        return

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    demandes = DemandeSolde.query.filter(
        DemandeSolde.envoyee_par == user_id,
        DemandeSolde.date_demande >= one_week_ago,
        DemandeSolde.etat.in_(["confirmé", "annulé"])
    ).all()

    confirmed = [d.to_dict() for d in demandes if d.etat == "confirmé"]
    cancelled = [d.to_dict() for d in demandes if d.etat == "annulé"]

    socketio.emit(
        "weekly_confirmed_and_cancelled",
        {"user_id": user_id, "confirmed": confirmed, "cancelled": cancelled},
        room=request.sid
    )

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

def emit_user_updated(user, exclude_user_id=None):
    """Helper function to emit user_updated event to relevant users."""
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

    sid = connected_users.get(str(user.id))
    if sid:
        socketio.emit('user_updated', {'user_id': user.id, 'data': user_data}, room=sid)
        print(f"Emitted user_updated to user {user.id} with SID {sid}")

    if user.responsable and user.responsable != exclude_user_id:
        sid = connected_users.get(str(user.responsable))
        if sid:
            socketio.emit('user_updated', {'user_id': user.id, 'data': user_data}, room=sid)
            print(f"Emitted user_updated to admin {user.responsable} with SID {sid}")

    managers = User.query.filter_by(role='manager').all()
    for manager in managers:
        if manager.id != exclude_user_id:
            sid = connected_users.get(str(manager.id))
            if sid:
                socketio.emit('user_updated', {'user_id': user.id, 'data': user_data}, room=sid)
                print(f"Emitted user_updated to manager {manager.id} with SID {sid}")

@demande_solde_bp.route('/add', methods=['POST'])
@jwt_required()
def create_demande_solde():
    raw_montant = request.form.get('montant')
    try:
        montant = float(raw_montant)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid montant"}), 400

    photo_file = request.files.get('preuve')
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role == "revendeur" and montant < 150.0:
        return jsonify({"error": "Revendeurs must request at least 150.0"}), 400

    new_request = DemandeSolde(envoyee_par=user.id, montant=montant)
    db.session.add(new_request)
    db.session.flush()

    if photo_file and photo_file.filename:
        folder = os.path.join(current_app.root_path, 'static', 'demande_solde', 'preuves')
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(photo_file.filename)[1] or '.png'
        filename = f"{new_request.id}{ext}"
        save_path = os.path.join(folder, filename)
        photo_file.save(save_path)
        new_request.preuve = os.path.relpath(save_path, current_app.root_path)

    db.session.commit()

    managers = User.query.filter_by(role='manager').all()
    for manager in managers:
        sid = connected_users.get(str(manager.id))
        if sid:
            socketio.emit(
                'new_demande_solde',
                {
                    "id": new_request.id,
                    "montant": montant,
                    "envoyee_par": user.nom,
                    "role": user.role,
                    "user_id": user.id
                },
                room=sid
            )
            count = get_en_cours_count(manager)
            socketio.emit("update_en_cours_count", {"user_id": manager.id, "count": count}, room=sid)

    if user.role == "revendeur" and user.responsable:
        admin = User.query.get(user.responsable)
        if admin:
            sid = connected_users.get(str(admin.id))
            if sid:
                socketio.emit(
                    'new_demande_solde',
                    {
                        "id": new_request.id,
                        "montant": montant,
                        "envoyee_par": user.nom,
                        "role": user.role,
                        "user_id": user.id
                    },
                    room=sid
                )
                count = get_en_cours_count(admin)
                socketio.emit("update_en_cours_count", {"user_id": admin.id, "count": count}, room=sid)

    return jsonify(new_request.to_dict()), 201
@demande_solde_bp.route('/get', methods=['GET'])
@jwt_required()
def get_all_demandes():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    search_query = request.args.get('search', type=str, default="").strip().lower()
    page = request.args.get('page', type=int, default=1)
    per_page = 20

    if user.role == "manager":
        query = DemandeSolde.query.join(User).filter(User.role == "admin")
    elif user.role == "admin":
        query = DemandeSolde.query.join(User).filter(User.responsable == user.id)
    else:
        return jsonify({"error": "Unauthorized access"}), 403

    if search_query:
        query = query.filter(
            db.or_(
                db.cast(DemandeSolde.montant, db.String).ilike(f"%{search_query}%"),
                DemandeSolde.etat.ilike(f"%{search_query}%"),
                User.nom.ilike(f"%{search_query}%")
            )
        )

    paginated = query.order_by(DemandeSolde.date_demande.desc()).paginate(page=page, per_page=per_page, error_out=False)
    demandes = paginated.items

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "demandes": [
            {**dem.to_dict(), "user_id": dem.envoyee_par}
            for dem in demandes
        ]
    }), 200


@demande_solde_bp.route('/update/<int:demande_id>', methods=['PUT'])
@jwt_required()
def update_demande(demande_id):
    data = request.get_json() or {}
    etat = data.get('etat')
    if etat not in ["confirmé", "annulé"]:
        return jsonify({"error": "Invalid state"}), 400

    user_id = get_jwt_identity()
    approver = User.query.get(user_id)
    if not approver:
        return jsonify({"error": "Approver not found"}), 404

    demande = DemandeSolde.query.get(demande_id)
    if not demande:
        return jsonify({"error": "Demande not found"}), 404

    requester = User.query.get(demande.envoyee_par)
    if not requester:
        return jsonify({"error": "Requester not found"}), 404

    if approver.role == "manager" and requester.role != "admin":
        return jsonify({"error": "Unauthorized: Managers can only approve admin requests."}), 403
    if approver.role == "admin" and (requester.role != "revendeur" or requester.responsable != approver.id):
        return jsonify({"error": "Unauthorized: Admins can only approve their own revendeurs' requests."}), 403
    if approver.role == "admin" and etat == "confirmé" and demande.montant > approver.solde:
        return jsonify({"error": "Insufficient solde"}), 400

    demande.etat = etat
    demande.date_traitement = datetime.utcnow()
    demande.traitee_par = approver.id

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
            "date_transaction": datetime.utcnow()
        }
        if demande.preuve:
            tx = TransactionPaye(preuve=demande.preuve, etat="paye", **tx_data)
        else:
            tx = TransactionImpaye(etat="impaye", **tx_data)
        db.session.add(tx)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Database commit failed for demande {demande_id}: {str(e)}")
        return jsonify({"error": "Database error occurred"}), 500

    if etat == "confirmé":
        db.session.refresh(requester)
        if approver.role == "admin":
            db.session.refresh(approver)
        emit_user_updated(requester, exclude_user_id=approver.id)
        if approver.role == "admin":
            emit_user_updated(approver, exclude_user_id=approver.id)

    users_to_notify_count = set([approver.id])
    if requester.role == "admin":
        managers = User.query.filter_by(role='manager').all()
        users_to_notify_count.update(manager.id for manager in managers)
    elif requester.role == "revendeur" and requester.responsable:
        users_to_notify_count.add(requester.responsable)

    for uid in users_to_notify_count:
        user = User.query.get(uid)
        sid = connected_users.get(str(uid))
        if sid:
            count = get_en_cours_count(user)
            socketio.emit("update_en_cours_count", {"user_id": uid, "count": count}, room=sid)
            print(f"Emitted update_en_cours_count to user {uid} with SID {sid}, count: {count}")

    requester_sid = connected_users.get(str(requester.id))
    if requester_sid:
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        demandes = DemandeSolde.query.filter(
            DemandeSolde.envoyee_par == requester.id,
            DemandeSolde.date_demande >= one_week_ago,
            DemandeSolde.etat.in_(["confirmé", "annulé"])
        ).all()
        confirmed = [d.to_dict() for d in demandes if d.etat == "confirmé"]
        cancelled = [d.to_dict() for d in demandes if d.etat == "annulé"]

        socketio.emit("weekly_confirmed_and_cancelled", {
            "user_id": requester.id,
            "confirmed": confirmed,
            "cancelled": cancelled
        }, room=requester_sid)
        print(f"Emitted weekly_confirmed_and_cancelled to requester {requester.id} with SID {requester_sid}")

    updated_data = demande.to_dict()
    socketio.emit("updated_demande", updated_data)
    print(f"Broadcasted updated_demande for demande {demande_id}")

    return jsonify(updated_data), 200