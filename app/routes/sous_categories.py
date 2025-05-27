# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from ..models.sous_category import SousCategory
from ..models.category import Category
from .. import db

sous_categories_bp = Blueprint('sous_categories', __name__)

@sous_categories_bp.route('/add_sous_category', methods=['POST'])
def add_sous_category():
    """Create a new sous category with category_id and upload image."""
    try:
        name = request.form.get('name')
        etat = request.form.get('etat', 'actif')
        category_id = request.form.get('category_id')
        photo_file = request.files.get('photo')

        if not name or not category_id:
            return jsonify({"error": "Name and category_id are required"}), 400

        category = Category.query.get(category_id)
        if not category:
            return jsonify({"message": "Category not found"}), 404

        new_sous_category = SousCategory(
            name=name,
            etat=etat,
            category_id=category.id
        )
        db.session.add(new_sous_category)
        db.session.flush()

        img_path = None
        if photo_file and photo_file.filename:
            folder = os.path.join(
                current_app.root_path,
                'static',
                'sous_categories_images',
                name.lower().replace(" ", "_")
            )
            os.makedirs(folder, exist_ok=True)

            filename = f"{new_sous_category.id}.png"
            save_path = os.path.join(folder, filename)

            if os.path.exists(save_path):
                os.remove(save_path)

            photo_file.save(save_path)
            img_path = os.path.relpath(save_path, current_app.root_path)

        new_sous_category.photo = img_path
        db.session.commit()

        return jsonify({
            "message": "SousCategory added successfully",
            "sous_category": new_sous_category.to_dict()
        }), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@sous_categories_bp.route('/get_sous_categories', methods=['GET'])
def get_all_sous_categories():
    """Retrieve all sous categories."""
    try:
        sous_categories = SousCategory.query.all()
        result = [sc.to_dict() for sc in sous_categories]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@sous_categories_bp.route('/get_sous_category/<int:id>', methods=['GET'])
def get_sous_category_by_id(id):
    """Retrieve a single sous category by its ID."""
    try:
        sous_category = SousCategory.query.get(id)
        if sous_category:
            return jsonify(sous_category.to_dict())
        return jsonify({"message": "SousCategory not found"}), 404
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500



@sous_categories_bp.route('/update_sous_category/<int:id>', methods=['PUT'])
def update_sous_category(id):
    """Update an existing sous category with new image if provided."""
    try:
        sous_category = SousCategory.query.get(id)
        if not sous_category:
            return jsonify({"message": "SousCategory not found"}), 404

        name = request.form.get('name', sous_category.name)
        etat = request.form.get('etat', sous_category.etat)
        category_id = request.form.get('category_id', sous_category.category_id)
        photo_file = request.files.get('photo')

        category = Category.query.get(category_id)
        if not category:
            return jsonify({"message": "Category not found"}), 404

        sous_category.name = name
        sous_category.etat = etat
        sous_category.category_id = category.id

        if photo_file and photo_file.filename:
            folder = os.path.join(
                current_app.root_path,
                'static',
                'sous_categories_images',
                name.lower().replace(" ", "_")
            )
            os.makedirs(folder, exist_ok=True)

            filename = f"{sous_category.id}.png"
            save_path = os.path.join(folder, filename)

            if os.path.exists(save_path):
                os.remove(save_path)

            photo_file.save(save_path)
            sous_category.photo = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()

        return jsonify({
            "message": "SousCategory updated successfully",
            "sous_category": sous_category.to_dict()
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500


@sous_categories_bp.route('/delete_sous_category/<int:id>', methods=['DELETE'])
def delete_sous_category(id):
    """Delete a sous category."""
    try:
        sous_category = SousCategory.query.get(id)
        if not sous_category:
            return jsonify({"message": "SousCategory not found"}), 404
        
        db.session.delete(sous_category)
        db.session.commit()
        
        return jsonify({"message": "SousCategory deleted successfully"})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
