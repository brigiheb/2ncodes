# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models.visible_item import VisibleItem, ItemType
from ..models.user import User

visible_bp = Blueprint('visible_items', __name__, url_prefix='/visible_items')


@visible_bp.route('/add', methods=['POST'])
@jwt_required()
def add_visible_item():
    """Manager assigns visible items to users."""
    user_id = request.json.get('user_id')
    item_id = request.json.get('item_id')
    item_type = request.json.get('item_type')

    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != "manager":
        return jsonify({"error": "Only managers can assign visibility."}), 403

    if not all([user_id, item_id, item_type]):
        return jsonify({"error": "Missing required fields."}), 400

    try:
        item_type_enum = ItemType(item_type)
    except ValueError:
        return jsonify({"error": "Invalid item type."}), 400

    new_visible = VisibleItem(
        user_id=user_id,
        item_id=item_id,
        item_type=item_type_enum
    )
    db.session.add(new_visible)
    db.session.commit()

    return jsonify({"message": "Visibility assigned", "data": new_visible.to_dict()}), 201


@visible_bp.route('/get_visible_items/<int:user_id>', methods=['GET'])
@jwt_required()
def get_visible_items(user_id):
    items = VisibleItem.query.filter_by(user_id=user_id).all()

    if not items:
        return jsonify({"message": "No visibility settings found for this user.", "user_id": user_id, "items": {}}), 200

    grouped = {}
    for item in items:
        item_type_str = item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type)
        if item_type_str not in grouped:
            grouped[item_type_str] = []
        grouped[item_type_str].append(item.item_id)

    return jsonify({
        "user_id": user_id,
        "items": grouped
    }), 200


@visible_bp.route('/delete/<int:visible_id>', methods=['DELETE'])
@jwt_required()
def delete_visible_item(visible_id):
    item = VisibleItem.query.get(visible_id)
    if not item:
        return jsonify({"error": "Item not found."}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Visibility removed."}), 200


@visible_bp.route('/add_multiple', methods=['POST'])
@jwt_required()
def add_visible_items_bulk():
    data = request.get_json()
    user_id = data.get('user_id')
    item_type = data.get('item_type')
    item_ids = data.get('item_ids')  # should be a list of integers

    if not user_id or not item_type or not isinstance(item_ids, list):
        return jsonify({"error": "Missing or invalid fields (user_id, item_type, item_ids)"}), 400

    # Optional: remove existing entries to overwrite
    db.session.query(VisibleItem).filter_by(user_id=user_id, item_type=item_type).delete()

    # Add all selected items
    for item_id in item_ids:
        db.session.add(VisibleItem(user_id=user_id, item_type=item_type, item_id=item_id))

    db.session.commit()
    return jsonify({"message": "Visible items updated successfully"}), 201


@visible_bp.route('/set_bulk', methods=['POST'])
@jwt_required()
def set_bulk_visible_items():
    data = request.get_json()
    user_id = data.get("user_id")
    items = data.get("items")

    if not user_id or not isinstance(items, dict):
        return jsonify({"error": "Invalid input format"}), 400

    # Delete all current visible items for this user
    VisibleItem.query.filter_by(user_id=user_id).delete()

    # Add new visible items
    for item_type, item_ids in items.items():
        if isinstance(item_ids, list):
            for item_id in item_ids:
                vi = VisibleItem(user_id=user_id, item_type=item_type, item_id=item_id)
                db.session.add(vi)

    db.session.commit()
    return jsonify({"message": "Visibility settings updated successfully."}), 200