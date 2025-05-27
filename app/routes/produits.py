# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from ..models.product import Produit
from ..models.category import Category
from ..models.sous_category import SousCategory
from .. import db
from ..models.duree_avec_stock import DureeAvecStock
import os
from flask import current_app
from werkzeug.utils import secure_filename

products_bp = Blueprint('products', __name__)

# Create a new product
@products_bp.route('/add_product', methods=['POST'])
def add_product():
    try:
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        sous_category_id = request.form.get('sous_category_id')
        etat = request.form.get('etat', 'actif')
        affichage = request.form.get('affichage')
        etat_commande = request.form.get('etat_commande', 'instantané')
        photo_file = request.files.get('photo')

        # Validate category
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"message": "Category not found"}), 404

        # Validate sous-category if provided
        sous_category = SousCategory.query.get(sous_category_id) if sous_category_id else None

        new_product = Produit(
            name=name,
            category_id=category.id,
            sous_category_id=sous_category.id if sous_category else None,
            etat=etat,
            affichage=affichage,
            etat_commande=etat_commande
        )

        db.session.add(new_product)
        db.session.flush()  # Get new_product.id before commit

        # Handle photo upload
        if photo_file and photo_file.filename:
            folder = os.path.join(current_app.root_path, 'static', 'products_images')
            os.makedirs(folder, exist_ok=True)

            filename = f"{new_product.id}.png"
            save_path = os.path.join(folder, secure_filename(filename))

            if os.path.exists(save_path):
                os.remove(save_path)
            photo_file.save(save_path)
            new_product.photo = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()
        return jsonify({
            "message": "Product added successfully",
            "product": new_product.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@products_bp.route('/get_products', methods=['GET'])
def get_all_products():
    try:
        # Get optional query parameters
        name = request.args.get('name')
        category_id = request.args.get('category_id')
        sous_category_id = request.args.get('sous_category_id')
        etat = request.args.get('etat')

        # Start building the query
        query = Produit.query

        if name:
            query = query.filter(Produit.name.ilike(f'%{name}%'))
        if category_id:
            query = query.filter(Produit.category_id == category_id)
        if sous_category_id:
            query = query.filter(Produit.sous_category_id == sous_category_id)
        if etat:
            query = query.filter(Produit.etat == etat)

        products = query.all()
        result = []
        for product in products:
            product_data = product.to_dict()
            product_data["duree_avec_stock"] = [d.to_dict() for d in product.duree_avec_stock]
            result.append(product_data)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get a product by ID
@products_bp.route('/get_product/<int:id>', methods=['GET'])
def get_product_by_id(id):
    try:
        product = Produit.query.get(id)
        if product:
            return jsonify(product.to_dict()), 200
        return jsonify({"message": "Product not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Update a product
@products_bp.route('/update_product/<int:id>', methods=['PUT'])
def update_product(id):
    try:
        product = Produit.query.get(id)
        if not product:
            return jsonify({"message": "Product not found"}), 404

        name = request.form.get('name')
        category_id = request.form.get('category_id')
        sous_category_id = request.form.get('sous_category_id')
        etat = request.form.get('etat')
        affichage = request.form.get('affichage')
        etat_commande = request.form.get('etat_commande')
        photo_file = request.files.get('photo')

        product.name = name or product.name
        product.category_id = category_id or product.category_id
        product.sous_category_id = sous_category_id or product.sous_category_id
        product.etat = etat or product.etat
        product.affichage = affichage or product.affichage
        product.etat_commande = etat_commande or product.etat_commande

        if photo_file and photo_file.filename:
            folder = os.path.join(current_app.root_path, 'static', 'products_images')
            os.makedirs(folder, exist_ok=True)

            filename = f"{product.id}.png"
            save_path = os.path.join(folder, secure_filename(filename))

            if os.path.exists(save_path):
                os.remove(save_path)
            photo_file.save(save_path)
            product.photo = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()
        return jsonify({
            "message": "Product updated successfully",
            "product": product.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Delete a product
@products_bp.route('/delete_product/<int:id>', methods=['DELETE'])
def delete_product(id):
    try:
        product = Produit.query.get(id)
        if not product:
            return jsonify({"message": "Product not found"}), 404

        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
