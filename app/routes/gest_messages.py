from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
from .. import db
from ..models.gest_message import GestMessage
from ..models.user import User
from app import socketio
from app.routes.demande_solde import connected_users

gest_message_bp = Blueprint('gest_message', __name__, url_prefix='/api/gest_message')

UPLOAD_FOLDER = os.path.join('static', 'messages')

# ===================== ADD MESSAGE ===================== #
@gest_message_bp.route('/add', methods=['POST'])
@jwt_required()
def add_message():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or user.role != "manager":
        return jsonify({"error": "Only managers can add messages."}), 403

    text = request.form.get('text')
    to = request.form.get('to')
    etat = request.form.get('etat', 'afficher')

    if not text or to not in ['admin', 'revendeur', 'all']:
        return jsonify({"error": "Missing 'text' or invalid 'to' value."}), 400

    new_msg = GestMessage(text=text, to=to, etat=etat)
    db.session.add(new_msg)
    db.session.flush()  # Get new_msg.id before saving files

    folder = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    os.makedirs(folder, exist_ok=True)

    # Handle image upload
    img_file = request.files.get('img')
    if img_file and img_file.filename:
        img_filename = secure_filename(f"{new_msg.id}.png")
        img_path = os.path.join(folder, img_filename)
        if os.path.exists(img_path):
            os.remove(img_path)
        img_file.save(img_path)
        new_msg.img_path = os.path.relpath(img_path, current_app.root_path)

    # Handle video upload
    video_file = request.files.get('video')
    if video_file and video_file.filename:
        video_filename = secure_filename(f"{new_msg.id}.mp4")
        video_path = os.path.join(folder, video_filename)
        if os.path.exists(video_path):
            os.remove(video_path)
        video_file.save(video_path)
        new_msg.video_path = os.path.relpath(video_path, current_app.root_path)

    # Handle file upload
    file_file = request.files.get('file')
    if file_file and file_file.filename:
        ext = os.path.splitext(file_file.filename)[-1]
        file_filename = secure_filename(f"{new_msg.id}{ext}")
        file_path = os.path.join(folder, file_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        file_file.save(file_path)
        new_msg.file_path = os.path.relpath(file_path, current_app.root_path)

    db.session.commit()

    payload = {
        "message_id": new_msg.id,
        "text": new_msg.text,
        "to": new_msg.to,
        "etat": new_msg.etat
    }

    roles = ['admin', 'revendeur'] if to == 'all' else [to]
    for role in roles:
        users = User.query.filter_by(role=role).all()
        for target in users:
            sid = connected_users.get(str(target.id))
            if sid:
                socketio.emit("new_message", payload, room=sid)

    return jsonify(new_msg.to_dict()), 201

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

    msg.text = request.form.get('text', msg.text)
    msg.to = request.form.get('to', msg.to)
    msg.etat = request.form.get('etat', msg.etat)

    folder = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    os.makedirs(folder, exist_ok=True)

    # Update image
    img_file = request.files.get('img')
    if img_file and img_file.filename:
        img_filename = secure_filename(f"{msg.id}.png")
        img_path = os.path.join(folder, img_filename)
        if os.path.exists(img_path):
            os.remove(img_path)
        img_file.save(img_path)
        msg.img_path = os.path.relpath(img_path, current_app.root_path)

    # Update video
    video_file = request.files.get('video')
    if video_file and video_file.filename:
        video_filename = secure_filename(f"{msg.id}.mp4")
        video_path = os.path.join(folder, video_filename)
        if os.path.exists(video_path):
            os.remove(video_path)
        video_file.save(video_path)
        msg.video_path = os.path.relpath(video_path, current_app.root_path)

    # Update general file
    file_file = request.files.get('file')
    if file_file and file_file.filename:
        ext = os.path.splitext(file_file.filename)[-1]
        file_filename = secure_filename(f"{msg.id}{ext}")
        file_path = os.path.join(folder, file_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        file_file.save(file_path)
        msg.file_path = os.path.relpath(file_path, current_app.root_path)

    db.session.commit()

    payload = msg.to_dict()
    target_roles = ['admin', 'revendeur'] if msg.to == 'all' else [msg.to]
    for role in target_roles:
        users = User.query.filter_by(role=role).all()
        for target_user in users:
            sid = connected_users.get(str(target_user.id))
            if sid:
                socketio.emit("message_updated", payload, room=sid)

    return jsonify(payload), 200

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

    # 🗑️ Remove associated files if present
    for path in [msg.img_path, msg.video_path, msg.file_path]:
        if path and os.path.exists(path):
            os.remove(path)

    payload = {"message_id": msg.id}
    target_roles = ['admin', 'revendeur'] if msg.to == 'all' else [msg.to]
    for role in target_roles:
        users = User.query.filter_by(role=role).all()
        for target_user in users:
            sid = connected_users.get(str(target_user.id))
            if sid:
                socketio.emit("message_deleted", payload, room=sid)

    db.session.delete(msg)
    db.session.commit()

    return jsonify({"message": "Message deleted successfully ✅"}), 200

# ===================== GET ALL MESSAGES (Manager only) ===================== #
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

# ===================== GET Admin Messages ===================== #
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

# ===================== GET Revendeur Messages ===================== #
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