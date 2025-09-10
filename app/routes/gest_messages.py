from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
from .. import db
from ..models.gest_message import GestMessage
from ..models.user import User
from app import socketio
from app.utils.socket_state import connected_users
from sqlalchemy import or_
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

gest_message_bp = Blueprint('gest_message', __name__, url_prefix='/api/gest_message')

# Helper function to emit message updates to relevant users
def emit_message_update(message, event_type):
    try:
        payload = message.to_dict()
        target_roles = ['admin', 'revendeur'] if message.to == 'all' else [message.to]
        for role in target_roles:
            users = User.query.filter_by(role=role).all()
            for target_user in users:
                sid = connected_users.get(str(target_user.id))
                if sid:
                    socketio.emit(event_type, payload, room=sid)
                    logger.debug(f"Emitted {event_type} to user {target_user.id} for message {message.id}")
                else:
                    logger.debug(f"No socket connection for user {target_user.id} for message {message.id}")
    except Exception as e:
        logger.error(f"Error emitting {event_type} for message {message.id}: {str(e)}")

# ===================== ADD MESSAGE ===================== #
@gest_message_bp.route('/add', methods=['POST'])
@jwt_required()
def add_message():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user or user.role not in ["manager", "admin_boss"]:
            logger.warning(f"Access denied for user_id={current_user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Only managers can add messages."}), 403

        text = request.form.get('text')
        to = request.form.get('to')
        etat = request.form.get('etat', 'afficher')

        if not text or to not in ['admin', 'revendeur', 'all']:
            return jsonify({"error": "Missing 'text' or invalid 'to' value."}), 400

        new_msg = GestMessage(text=text, to=to, etat=etat)
        db.session.add(new_msg)
        db.session.flush()  # Get new_msg.id before saving files

        folder = os.path.join(current_app.root_path, 'static', 'messages')
        os.makedirs(folder, exist_ok=True)

        img_file = request.files.get('img')
        if img_file and img_file.filename:
            filename = f"{new_msg.id}.png"
            save_path = os.path.join(folder, filename)
            if os.path.exists(save_path):
                os.remove(save_path)
            img_file.save(save_path)
            new_msg.img_path = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()

        # Emit new message to relevant users
        emit_message_update(new_msg, 'new_message')

        return jsonify(new_msg.to_dict()), 201
    except Exception as e:
        logger.error(f"Error in add_message: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# ===================== UPDATE MESSAGE ===================== #
@gest_message_bp.route('/update/<int:id>', methods=['PUT'])
@jwt_required()
def update_message(id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        msg = GestMessage.query.get(id)

        if not user or user.role not in ["manager", "admin_boss"]:
            logger.warning(f"Access denied for user_id={current_user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Only managers can update messages."}), 403
        if not msg:
            logger.warning(f"Message not found: id={id}")
            return jsonify({"error": "Message not found"}), 404

        msg.text = request.form.get('text', msg.text)
        msg.to = request.form.get('to', msg.to)
        msg.etat = request.form.get('etat', msg.etat)

        folder = os.path.join(current_app.root_path, 'static', 'messages')
        os.makedirs(folder, exist_ok=True)

        img_file = request.files.get('img')
        if img_file and img_file.filename:
            filename = f"{msg.id}.png"
            save_path = os.path.join(folder, filename)
            if os.path.exists(save_path):
                os.remove(save_path)
            img_file.save(save_path)
            msg.img_path = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()

        # Emit updated message to relevant users
        emit_message_update(msg, 'message_updated')

        return jsonify(msg.to_dict()), 200
    except Exception as e:
        logger.error(f"Error in update_message: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# ===================== DELETE MESSAGE ===================== #
@gest_message_bp.route('/delete/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_message(id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        msg = GestMessage.query.get(id)

        if not user or user.role not in ["manager", "admin_boss"]:
            logger.warning(f"Access denied for user_id={current_user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Only managers can delete messages."}), 403
        if not msg:
            logger.warning(f"Message not found: id={id}")
            return jsonify({"error": "Message not found"}), 404

        # Remove associated files if present
        for path in [msg.img_path, msg.video_path, msg.file_path]:
            if path and os.path.exists(path):
                os.remove(path)

        # Emit deletion event to relevant users
        payload = {"message_id": msg.id}
        target_roles = ['admin', 'revendeur'] if msg.to == 'all' else [msg.to]
        for role in target_roles:
            users = User.query.filter_by(role=role).all()
            for target_user in users:
                sid = connected_users.get(str(target_user.id))
                if sid:
                    socketio.emit("message_deleted", payload, room=sid)
                    logger.debug(f"Emitted message_deleted to user {target_user.id} for message {msg.id}")

        db.session.delete(msg)
        db.session.commit()

        return jsonify({"message": "Message deleted successfully ✅"}), 200
    except Exception as e:
        logger.error(f"Error in delete_message: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# ===================== GET ALL MESSAGES (Manager only) ===================== #
@gest_message_bp.route('/all_msg', methods=['GET'])
@jwt_required()
def get_all_messages_unfiltered():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user or user.role not in ["manager", "admin_boss"]:
            logger.warning(f"Access denied for user_id={current_user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Only managers can view all messages."}), 403

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str).strip()
        to = request.args.get('to', None, type=str)

        query = GestMessage.query

        if search:
            query = query.filter(GestMessage.text.ilike(f'%{search}%'))
        
        if to and to in ['admin', 'revendeur', 'all']:
            query = query.filter(GestMessage.to == to)

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        messages = pagination.items

        return jsonify({
            'messages': [msg.to_dict() for msg in messages],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        }), 200
    except Exception as e:
        logger.error(f"Error in get_all_messages_unfiltered: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# ===================== GET ONE MESSAGE ===================== #
@gest_message_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_message(id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        msg = GestMessage.query.get(id)

        if not msg:
            logger.warning(f"Message not found: id={id}")
            return jsonify({"error": "Message not found"}), 404

        if msg.etat != 'afficher' or (msg.to != user.role and msg.to != 'all'):
            logger.warning(f"Access denied for user_id={current_user_id} to view message {id}")
            return jsonify({"error": "You are not allowed to view this message"}), 403

        return jsonify(msg.to_dict()), 200
    except Exception as e:
        logger.error(f"Error in get_message: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# ===================== GET Admin Messages ===================== #
@gest_message_bp.route('/admin_messages', methods=['GET'])
@jwt_required()
def get_admin_messages():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user or user.role != "admin":
            logger.warning(f"Access denied for user_id={current_user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access restricted to admins only."}), 403

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str).strip()

        query = GestMessage.query.filter(
            or_(GestMessage.to == 'admin', GestMessage.to == 'all'),
            GestMessage.etat == 'afficher'
        )

        if search:
            query = query.filter(GestMessage.text.ilike(f'%{search}%'))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        messages = pagination.items

        return jsonify({
            'messages': [msg.to_dict() for msg in messages],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        }), 200
    except Exception as e:
        logger.error(f"Error in get_admin_messages: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# ===================== GET Revendeur Messages ===================== #
@gest_message_bp.route('/revendeur_messages', methods=['GET'])
@jwt_required()
def get_revendeur_messages():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user or user.role != "revendeur":
            logger.warning(f"Access denied for user_id={current_user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access restricted to revendeurs only."}), 403

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str).strip()

        query = GestMessage.query.filter(
            or_(GestMessage.to == 'revendeur', GestMessage.to == 'all'),
            GestMessage.etat == 'afficher'
        )

        if search:
            query = query.filter(GestMessage.text.ilike(f'%{search}%'))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        messages = pagination.items

        return jsonify({
            'messages': [msg.to_dict() for msg in messages],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        }), 200
    except Exception as e:
        logger.error(f"Error in get_revendeur_messages: {str(e)}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500