from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import base64
from datetime import datetime
from .. import db
from ..models.gest_message import GestMessage
from ..models.user import User
from app import socketio

gest_message_bp = Blueprint('gest_message', __name__, url_prefix='/api/gest_message')

UPLOAD_FOLDER = 'static/messages/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Utility to save a base64-encoded file
def save_base64_file(base64_str, prefix, extension):
    filename = f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{extension}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    with open(path, "wb") as f:
        f.write(base64.b64decode(base64_str))
    return path

# ===================== ADD MESSAGE ===================== #
@gest_message_bp.route('/add', methods=['POST'])
@jwt_required()
def add_message():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or user.role != "manager":
        return jsonify({"error": "Only managers can add messages."}), 403

    data = request.get_json()
    text = data.get('text')
    to = data.get('to')
    etat = data.get('etat', 'afficher')

    img_path = data.get('img_path')
    video_path = data.get('video_path')
    file_path = data.get('file_path')

    if not text or to not in ['admin', 'revendeur', 'all']:
        return jsonify({"error": "Missing 'text' or invalid 'to' value."}), 400

    new_msg = GestMessage(
        text=text,
        to=to,
        etat=etat,
        img_path=img_path,
        video_path=video_path,
        file_path=file_path
    )

    db.session.add(new_msg)
    db.session.commit()

    # ✅ Real-time socket notification
    socketio.emit("new_message", {
        "message_id": new_msg.id,
        "text": new_msg.text,
        "to": new_msg.to,
        "etat": new_msg.etat
    })

    return jsonify(new_msg.to_dict()), 201

# ===================== GET ALL MESSAGES (manager only) ===================== #
@gest_message_bp.route('/all_msg', methods=['GET'])
@jwt_required()
def get_all_messages_unfiltered():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or user.role != 'manager':
        return jsonify({"error": "Only managers can view all messages."}), 403

    messages = GestMessage.query.all()
    return jsonify([msg.to_dict() for msg in messages]), 200

# ===================== GET ONE MESSAGE ===================== #
@gest_message_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_message(id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    msg = GestMessage.query.get(id)

    if not msg:
        return jsonify({"error": "Message not found"}), 404

    if msg.etat != 'afficher' or (msg.to != user.role and msg.to != 'all'):
        return jsonify({"error": "You are not allowed to view this message"}), 403

    return jsonify(msg.to_dict()), 200

# ===================== UPDATE MESSAGE ===================== #
@gest_message_bp.route('/update/<int:id>', methods=['PUT'])
@jwt_required()
def update_message(id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    msg = GestMessage.query.get(id)

    if not user or user.role != 'manager':
        return jsonify({"error": "Only managers can update messages."}), 403
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    data = request.get_json()

    msg.text = data.get('text', msg.text)
    msg.to = data.get('to', msg.to)
    msg.etat = data.get('etat', msg.etat)

    db.session.commit()
    return jsonify(msg.to_dict()), 200

# ===================== DELETE MESSAGE ===================== #
@gest_message_bp.route('/delete/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_message(id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    msg = GestMessage.query.get(id)

    if not user or user.role != 'manager':
        return jsonify({"error": "Only managers can delete messages."}), 403
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    for path in [msg.img_path, msg.video_path, msg.file_path]:
        if path and os.path.exists(path):
            os.remove(path)

    db.session.delete(msg)
    db.session.commit()
    return jsonify({"message": "Message deleted successfully ✅"}), 200

# ===================== Get MESSAGE Admin ===================== #
@gest_message_bp.route('/admin_messages', methods=['GET'])
@jwt_required()
def get_admin_messages():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or user.role != "admin":
        return jsonify({"error": "Access restricted to admins only."}), 403

    messages = GestMessage.query.filter(
        (GestMessage.to == 'admin') | (GestMessage.to == 'all'),
        GestMessage.etat == 'afficher'
    ).all()

    return jsonify([msg.to_dict() for msg in messages]), 200

# ===================== Get MESSAGE Revendeur ===================== #
@gest_message_bp.route('/revendeur_messages', methods=['GET'])
@jwt_required()
def get_revendeur_messages():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or user.role != "revendeur":
        return jsonify({"error": "Access restricted to revendeurs only."}), 403

    messages = GestMessage.query.filter(
        (GestMessage.to == 'revendeur') | (GestMessage.to == 'all'),
        GestMessage.etat == 'afficher'
    ).all()

    return jsonify([msg.to_dict() for msg in messages]), 200
