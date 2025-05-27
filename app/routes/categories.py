# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, current_app
from ..models.category import Category
from .. import db
from werkzeug.utils import secure_filename
from datetime import datetime
import os 

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/add_category', methods=['POST'])
def add_category():
    nom = request.form.get('nom')
    etat = request.form.get('etat', 'actif')
    photo_file = request.files.get('photo')

    print(f"[DEBUG] Received nom: {nom}")
    print(f"[DEBUG] Received etat: {etat}")
    print(f"[DEBUG] Received file: {photo_file.filename if photo_file else 'No file'}")

    if not nom:
        print("[ERROR] No category name provided.")
        return jsonify({"error": "Category name is required"}), 400

    # Create category to get ID first
    new_category = Category(nom=nom, etat=etat)
    db.session.add(new_category)
    db.session.flush()  # Retrieve ID before commit
    print(f"[DEBUG] Created new category with temporary ID: {new_category.id}")

    img_path = None
    if photo_file and photo_file.filename:
        # Format folder path
        folder = os.path.join(
            current_app.root_path,
            'static',
            'categories_images',
            nom.lower().replace(" ", "_")
        )
        print(f"[DEBUG] Saving image to folder: {folder}")
        os.makedirs(folder, exist_ok=True)

        filename = f"{new_category.id}.png"
        save_path = os.path.join(folder, filename)
        print(f"[DEBUG] Final save path: {save_path}")

        # Remove previous image if exists
        if os.path.exists(save_path):
            print(f"[INFO] Existing file found. Removing: {save_path}")
            os.remove(save_path)

        # Save new image
        photo_file.save(save_path)
        img_path = os.path.relpath(save_path, current_app.root_path)
        print(f"[DEBUG] Image saved at: {img_path}")

    new_category.photo = img_path
    db.session.commit()
    print(f"[SUCCESS] Category added and committed with ID: {new_category.id}")

    return jsonify({
        "message": "Category added successfully",
        "category": new_category.to_dict()
    }), 201


@categories_bp.route('/get_category', methods=['GET'])
def get_all_categories():
    categories = Category.query.all()
    result = [category.to_dict() for category in categories]
    return jsonify(result)

@categories_bp.route('/get_category/<int:id>', methods=['GET'])
def get_category_by_id(id):
    category = Category.query.get(id)
    if category:
        return jsonify(category.to_dict())
    return jsonify({"message": "Category not found"}), 404

@categories_bp.route('/put_category/<int:id>', methods=['PUT'])
def update_category(id):
    category = Category.query.get(id)
    if not category:
        return jsonify({"message": "Category not found"}), 404

    nom = request.form.get('nom', category.nom)
    etat = request.form.get('etat', category.etat)
    photo_file = request.files.get('photo')

    category.nom = nom
    category.etat = etat

    if photo_file and photo_file.filename:
        folder = os.path.join(
            current_app.root_path,
            'static',
            'categories_images',
            nom.lower().replace(" ", "_")
        )
        os.makedirs(folder, exist_ok=True)

        filename = f"{category.id}.png"
        save_path = os.path.join(folder, filename)

        if os.path.exists(save_path):
            os.remove(save_path)

        photo_file.save(save_path)
        category.photo = os.path.relpath(save_path, current_app.root_path)

    db.session.commit()
    return jsonify({"message": "Category updated successfully", "category": category.to_dict()}), 200




@categories_bp.route('/delete_category/<int:id>', methods=['DELETE'])
def delete_category(id):
    print(f"[DEBUG] Attempting to delete category with ID: {id}")

    category = Category.query.get(id)
    if not category:
        print(f"[ERROR] Category with ID {id} not found.")
        return jsonify({"message": "Category not found"}), 404

    # Delete associated image if it exists
    if category.photo:
        photo_path = os.path.join(current_app.root_path, category.photo)
        print(f"[DEBUG] Attempting to delete image at: {photo_path}")
        if os.path.isfile(photo_path):
            try:
                os.remove(photo_path)
                print(f"[SUCCESS] Image deleted: {photo_path}")
            except Exception as e:
                print(f"[WARNING] Failed to delete image: {e}")
        else:
            print(f"[INFO] Image file not found at: {photo_path}")
    else:
        print("[INFO] No image associated with this category.")

    # Delete the category and commit
    try:
        db.session.delete(category)
        db.session.commit()
        print(f"[SUCCESS] Category with ID {id} deleted from database.")
        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to delete category from DB: {e}")
        return jsonify({
            "error": "Failed to delete category",
            "details": str(e)
        }), 500

