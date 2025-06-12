# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db, socketio
from ..models.visible_item import VisibleItem, ItemType
from ..models.user import User
from ..utils.socket_state import connected_users

visible_bp = Blueprint('visible_items', __name__, url_prefix='/visible_items')

def get_grouped_visible_items(user_id):
    """Helper function to fetch and group visible items for a user."""
    items = VisibleItem.query.filter_by(user_id=user_id).all()
    grouped = {}
    for item in items:
        item_type_str = item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type)
        if item_type_str not in grouped:
            grouped[item_type_str] = []
        grouped[item_type_str].append(item.item_id)
    return grouped

def emit_visible_items_updated(user_id, exclude_user_id=None):
    """Helper function to emit visible_items_updated event to relevant users."""
    user = User.query.get(user_id)
    if not user:
        return

    grouped_items = get_grouped_visible_items(user_id)
    data = {
        "user_id": user_id,
        "items": grouped_items
    }

    # Notify the user
    sid = connected_users.get(str(user_id))
    if sid:
        socketio.emit('visible_items_updated', data, room=sid)
        print(f"Emitted visible_items_updated to user {user_id} with SID {sid}")

    # Notify all managers (except exclude_user_id)
    managers = User.query.filter_by(role='manager').all()
    for manager in managers:
        if manager.id != exclude_user_id:
            sid = connected_users.get(str(manager.id))
            if sid:
                socketio.emit('visible_items_updated', data, room=sid)
                print(f"Emitted visible_items_updated to manager {manager.id} with SID {sid}")

# ===================== SOCKET EVENTS ===================== #

@socketio.on('get_visible_items')
def socket_get_visible_items(data):
    """Socket event to fetch visible items for a user in real-time."""
    user_id = data.get('user_id')
    current_user_id = data.get('current_user_id')  # Optional: for authorization check
    user = User.query.get(user_id)
    current_user = User.query.get(current_user_id) if current_user_id else None

    if not user:
        socketio.emit('visible_items_error', {'error': 'User not found'}, room=request.sid)
        return

    # Authorization: Only the user themselves or managers can fetch visible items
    if current_user and current_user.id != user_id and current_user.role != 'manager':
        socketio.emit('visible_items_error', {'error': 'Unauthorized'}, room=request.sid)
        return

    grouped_items = get_grouped_visible_items(user_id)
    socketio.emit('visible_items_updated', {
        'user_id': user_id,
        'items': grouped_items
    }, room=request.sid)
    print(f"Emitted visible_items_updated to SID {request.sid} for user {user_id}")

# ===================== HTTP ENDPOINTS ===================== #

@visible_bp.route('/add', methods=['POST'])
@jwt_required()
def add_visible_item():
    """Manager assigns a single visible item to a user."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if current_user.role != "manager":
        return jsonify({"error": "Only managers can assign visibility."}), 403

    user_id = request.json.get('user_id')
    item_id = request.json.get('item_id')
    item_type = request.json.get('item_type')

    if not all([user_id, item_id, item_type]):
        return jsonify({"error": "Missing required fields."}), 400

    try:
        item_type_enum = ItemType(item_type)
    except ValueError:
        return jsonify({"error": "Invalid item type."}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    new_visible = VisibleItem(
        user_id=user_id,
        item_id=item_id,
        item_type=item_type_enum
    )
    db.session.add(new_visible)
    db.session.commit()

    # Emit update to the user and managers
    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visibility assigned", "data": new_visible.to_dict()}), 201

@visible_bp.route('/get_visible_items/<int:user_id>', methods=['GET'])
@jwt_required()
def get_visible_items(user_id):
    """Fetch visible items for a user via HTTP."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found."}), 404

    if current_user.id != user_id and current_user.role not in ['manager', 'admin']:
        return jsonify({"error": "Unauthorized."}), 403

    grouped = get_grouped_visible_items(user_id)
    return jsonify({
        "user_id": user_id,
        "items": grouped if grouped else {}
    }), 200

@visible_bp.route('/delete/<int:visible_id>', methods=['DELETE'])
@jwt_required()
def delete_visible_item(visible_id):
    """Manager deletes a visible item for a user."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if current_user.role != "manager":
        return jsonify({"error": "Only managers can delete visibility."}), 403

    item = VisibleItem.query.get(visible_id)
    if not item:
        return jsonify({"error": "Item not found."}), 404

    user_id = item.user_id
    db.session.delete(item)
    db.session.commit()

    # Emit update to the user and managers
    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visibility removed."}), 200

@visible_bp.route('/add_multiple', methods=['POST'])
@jwt_required()
def add_visible_items_bulk():
    """Manager assigns multiple visible items of the same type to a user."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if current_user.role != "manager":
        return jsonify({"error": "Only managers can assign visibility."}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    item_type = data.get('item_type')
    item_ids = data.get('item_ids')

    if not user_id or not item_type or not isinstance(item_ids, list):
        return jsonify({"error": "Missing or invalid fields (user_id, item_type, item_ids)"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        item_type_enum = ItemType(item_type)
    except ValueError:
        return jsonify({"error": "Invalid item type."}), 400

    # Remove existing entries for this user and item type
    db.session.query(VisibleItem).filter_by(user_id=user_id, item_type=item_type).delete()

    # Add new visible items
    for item_id in item_ids:
        db.session.add(VisibleItem(user_id=user_id, item_type=item_type_enum, item_id=item_id))

    db.session.commit()

    # Emit update to the user and managers
    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visible items updated successfully"}), 201

@visible_bp.route('/set_bulk', methods=['POST'])
@jwt_required()
def set_bulk_visible_items():
    """Manager sets all visible items for a user, replacing existing ones."""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if current_user.role not in ['manager', 'admin']:
        return jsonify({"error": "Only managers can set visibility."}), 403

    data = request.get_json()
    user_id = data.get("user_id")
    items = data.get("items")

    if not user_id or not isinstance(items, dict):
        return jsonify({"error": "Invalid input format"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    # Delete all current visible items for this user
    VisibleItem.query.filter_by(user_id=user_id).delete()

    # Add new visible items
    for item_type, item_ids in items.items():
        try:
            item_type_enum = ItemType(item_type)
        except ValueError:
            return jsonify({"error": f"Invalid item type: {item_type}"}), 400

        if isinstance(item_ids, list):
            for item_id in item_ids:
                vi = VisibleItem(user_id=user_id, item_type=item_type_enum, item_id=item_id)
                db.session.add(vi)

    db.session.commit()

    # Emit update to the user and managers
    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visibility settings updated successfully."}), 200