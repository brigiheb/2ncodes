# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, current_app
from ..models.category import Category
from ..models.user import User
from ..models.visible_item import VisibleItem, ItemType
from .. import db
from werkzeug.utils import secure_filename
from datetime import datetime
import os 
from ..models.product import Produit  # make sure this import is correct


categories_bp = Blueprint('categories', __name__)

def add_category_to_all_users_visible_items(category_id):
    users = User.query.all()
    for user in users:
        visible_item = VisibleItem(
            user_id=user.id,
            item_id=category_id,
            item_type=ItemType.category
        )
        db.session.add(visible_item)
    db.session.commit()

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

        if os.path.exists(save_path):
            print(f"[INFO] Existing file found. Removing: {save_path}")
            os.remove(save_path)

        photo_file.save(save_path)
        img_path = os.path.relpath(save_path, current_app.root_path)
        print(f"[DEBUG] Image saved at: {img_path}")

    new_category.photo = img_path
    db.session.commit()
    print(f"[SUCCESS] Category added and committed with ID: {new_category.id}")

    # Add the new category to all users' visible items
    add_category_to_all_users_visible_items(new_category.id)
    print(f"[SUCCESS] Added category {new_category.id} to all users' visible items")

    return jsonify({
        "message": "Category added successfully",
        "category": new_category.to_dict()
    }), 201


@categories_bp.route('/get_category', methods=['GET'])
def get_all_categories():
    """
    Retrieve categories, sorted by ID descending, with optional pagination, filtering, and search.
    Returns all categories if no parameters are provided.
    """
    try:
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=None)
        limit = request.args.get('per_page', type=int, default=None)
        filters = {
            key: value for key, value in request.args.items()
            if key not in ['search', 'page', 'per_page']
        }

        query = Category.query

        # Apply filters (e.g., ?etat=actif)
        for field, value in filters.items():
            if hasattr(Category, field):
                query = query.filter(getattr(Category, field).ilike(f"%{value}%"))

        # Apply search on 'nom'
        if search_query:
            query = query.filter(Category.nom.ilike(f"%{search_query}%"))

        # If no pagination parameters are provided, return all results
        if page is None and limit is None:
            categories = query.order_by(Category.id.desc()).all()
            return jsonify({
                "total": len(categories),
                "categories": [category.to_dict() for category in categories]
            }), 200

        # Apply pagination if parameters are provided
        limit = limit or 20  # Default to 20 if not specified
        page = page or 1     # Default to 1 if not specified
        paginated = query.order_by(Category.id.desc()).paginate(page=page, per_page=limit, error_out=False)
        categories = paginated.items

        return jsonify({
            "page": page,
            "per_page": limit,
            "total": paginated.total,
            "pages": paginated.pages,
            "categories": [category.to_dict() for category in categories]
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
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

    # Delete all products associated with the category
    try:
        products = Produit.query.filter_by(category_id=id).all()
        print(f"[DEBUG] Found {len(products)} products with category_id {id}")
        for product in products:
            db.session.delete(product)
        print(f"[SUCCESS] Deleted {len(products)} products associated with category_id {id}")
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to delete products: {e}")
        return jsonify({
            "error": "Failed to delete associated products",
            "details": str(e)
        }), 500

    # Delete the category
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