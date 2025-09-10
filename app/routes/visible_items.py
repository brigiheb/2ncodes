# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db, socketio
from ..models.visible_item import VisibleItem, ItemType
from ..models.user import User
from ..utils.socket_state import connected_users
from ..models.product import Produit
from ..models.category import Category
from ..models.sous_category import SousCategory
from ..models.boutique import Boutique
from ..models.article import Article
from ..models.application import Application

visible_bp = Blueprint('visible_items', __name__, url_prefix='/visible_items')

def assign_all_visible_items_to_user(user_id):
    items = []
    items += [(p.id, ItemType.product) for p in Produit.query.all()]
    items += [(c.id, ItemType.category) for c in Category.query.all()]
    items += [(s.id, ItemType.sous_category) for s in SousCategory.query.all()]
    items += [(b.id, ItemType.boutique) for b in Boutique.query.all()]
    items += [(a.id, ItemType.article) for a in Article.query.all()]
    items += [(app.id, ItemType.application) for app in Application.query.all()]

    for item_id, item_type in items:
        db.session.add(VisibleItem(user_id=user_id, item_id=item_id, item_type=item_type))
    db.session.commit()

def get_grouped_visible_items(user_id):
    # Fetch all visible items for the user and organize them by type
    visible_items = VisibleItem.query.filter_by(user_id=user_id).all()
    
    # Create a dictionary of sets for each item type
    visible_items_by_type = {
        ItemType.category: set(),
        ItemType.sous_category: set(),
        ItemType.boutique: set(),
        ItemType.application: set()
    }
    
    for item in visible_items:
        if item.item_type in visible_items_by_type:
            visible_items_by_type[item.item_type].add(item.item_id)

    grouped = {
        'category': [],
        'sous_category': [],
        'boutique': [],
        'application': []
    }

    # Categories
    for category in Category.query.all():
        grouped['category'].append({
            'id': category.id,
            'nom': category.nom,
            'selected': category.id in visible_items_by_type[ItemType.category]
        })

    # Sous Categories
    for sous_category in SousCategory.query.all():
        category = Category.query.get(sous_category.category_id)
        category_name = category.nom if category else "Unknown Category"
        grouped['sous_category'].append({
            'id': sous_category.id,
            'name': sous_category.name,
            'category_id': sous_category.category_id,
            'category_name': category_name,
            'selected': sous_category.id in visible_items_by_type[ItemType.sous_category]
        })

    # Boutiques
    for boutique in Boutique.query.all():
        grouped['boutique'].append({
            'id': boutique.id,
            'nom': boutique.nom,
            'selected': boutique.id in visible_items_by_type[ItemType.boutique]
        })

    # Applications
    for application in Application.query.all():
        grouped['application'].append({
            'id': application.id,
            'nom': application.nom,
            'selected': application.id in visible_items_by_type[ItemType.application]
        })

    return grouped

# ===================== SOCKET FUNCTIONS ===================== #

def emit_visible_items_updated(user_id, exclude_user_id=None):
    user = User.query.get(user_id)
    if not user:
        return

    try:
        grouped_items = get_grouped_visible_items(user_id)
        data = {
            "user_id": user_id,
            "items": grouped_items
        }

        sid = connected_users.get(str(user_id))
        if sid:
            socketio.emit('visible_items_updated', data, room=sid)
            print(f"Emitted visible_items_updated to user {user_id} with SID {sid}")

        managers = User.query.filter_by(role='manager').all()
        for manager in managers:
            if manager.id != exclude_user_id:
                sid = connected_users.get(str(manager.id))
                if sid:
                    socketio.emit('visible_items_updated', data, room=sid)
                    print(f"Emitted visible_items_updated to manager {manager.id} with SID {sid}")
    except Exception as e:
        print(f"Error in emit_visible_items_updated for user {user_id}: {str(e)}")

# ===================== SOCKET EVENTS ===================== #

@socketio.on('get_visible_items')
def socket_get_visible_items(data):
    user_id = data.get('user_id')
    current_user_id = data.get('current_user_id')
    user = User.query.get(user_id)
    current_user = User.query.get(current_user_id) if current_user_id else None

    if not user:
        socketio.emit('visible_items_error', {'error': 'User not found'}, room=request.sid)
        return

    if current_user and current_user.id != user_id and current_user.role != 'manager':
        socketio.emit('visible_items_error', {'error': 'Unauthorized'}, room=request.sid)
        return

    try:
        grouped_items = get_grouped_visible_items(user_id)
        socketio.emit('visible_items_updated', {
            'user_id': user_id,
            'items': grouped_items
        }, room=request.sid)
        print(f"Emitted visible_items_updated to SID {request.sid} for user {user_id}")
    except Exception as e:
        socketio.emit('visible_items_error', {'error': f"Failed to fetch visible items: {str(e)}"}, room=request.sid)
        print(f"Error in socket_get_visible_items for user {user_id}: {str(e)}")

# ===================== HTTP ENDPOINTS ===================== #

@visible_bp.route('/add', methods=['POST'])
@jwt_required()
def add_visible_item():
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

    try:
        item_id = int(item_id)  # Ensure item_id is an integer
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid item_id, must be an integer."}), 400

    new_visible = VisibleItem(
        user_id=user_id,
        item_id=item_id,
        item_type=item_type_enum
    )
    db.session.add(new_visible)
    db.session.commit()

    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visibility assigned", "data": new_visible.to_dict()}), 201

@visible_bp.route('/get_visible_items/<int:user_id>', methods=['GET'])
@jwt_required()
def get_visible_items(user_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found."}), 404

    if current_user.id != user_id and current_user.role not in ['manager', 'admin']:
        return jsonify({"error": "Unauthorized."}), 403

    try:
        grouped = get_grouped_visible_items(user_id)
        return jsonify({
            "user_id": user_id,
            "items": grouped if grouped else {}
        }), 200
    except Exception as e:
        print(f"Error in get_visible_items for user {user_id}: {str(e)}")
        return jsonify({"error": f"Failed to fetch visible items: {str(e)}"}), 500

@visible_bp.route('/delete/<int:visible_id>', methods=['DELETE'])
@jwt_required()
def delete_visible_item(visible_id):
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

    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visibility removed."}), 200

@visible_bp.route('/add_multiple', methods=['POST'])
@jwt_required()
def add_visible_items_bulk():
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

    db.session.query(VisibleItem).filter_by(user_id=user_id, item_type=item_type).delete()

    for item_id in item_ids:
        try:
            item_id = int(item_id)  # Ensure item_id is an integer
            db.session.add(VisibleItem(user_id=user_id, item_type=item_type_enum, item_id=item_id))
        except (ValueError, TypeError):
            print(f"Skipping invalid item_id {item_id} for user {user_id} and type {item_type}")
            continue

    db.session.commit()
    emit_visible_items_updated(user_id, exclude_user_id=current_user_id)

    return jsonify({"message": "Visible items updated successfully"}), 201

@visible_bp.route('/set_bulk', methods=['POST'])
@jwt_required()
def set_bulk_visible_items():
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

    try:
        # First delete all existing visible items for this user
        VisibleItem.query.filter_by(user_id=user_id).delete()

        # Prepare lists for each item type
        selected_categories = items.get('category', [])
        selected_sous_categories = items.get('sous_category', [])
        selected_boutiques = items.get('boutique', [])
        selected_applications = items.get('application', [])

        # Add categories
        for cat_id in selected_categories:
            if Category.query.get(cat_id):  # Only add if category exists
                db.session.add(VisibleItem(
                    user_id=user_id,
                    item_type=ItemType.category,
                    item_id=cat_id
                ))

        # Add sous categories (with basic validation)
        for sc_id in selected_sous_categories:
            sc = SousCategory.query.get(sc_id)
            if sc and sc.category_id in selected_categories:  # Only add if exists and parent category is selected
                db.session.add(VisibleItem(
                    user_id=user_id,
                    item_type=ItemType.sous_category,
                    item_id=sc_id
                ))

        # Add boutiques
        for bout_id in selected_boutiques:
            if Boutique.query.get(bout_id):  # Only add if boutique exists
                db.session.add(VisibleItem(
                    user_id=user_id,
                    item_type=ItemType.boutique,
                    item_id=bout_id
                ))

        # Add applications
        for app_id in selected_applications:
            if Application.query.get(app_id):  # Only add if application exists
                db.session.add(VisibleItem(
                    user_id=user_id,
                    item_type=ItemType.application,
                    item_id=app_id
                ))

        db.session.commit()
        emit_visible_items_updated(user_id, exclude_user_id=current_user_id)
        return jsonify({"message": "Visibility settings updated successfully."}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating visible items: {str(e)}")
        return jsonify({"error": f"Failed to update visible items: {str(e)}"}), 500