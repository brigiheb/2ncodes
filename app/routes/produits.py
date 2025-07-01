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
from sqlalchemy.sql import func, asc, desc
from sqlalchemy import case

products_bp = Blueprint('products', __name__)

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

        category = Category.query.get(category_id)
        if not category:
            return jsonify({"message": "Category not found"}), 404

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
        db.session.flush()

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
    """Retrieve all products with pagination, filtering, and sorting."""
    try:
        search = request.args.get('search', type=str, default="").strip()
        category_id = request.args.get('category_id', type=int)
        sous_category_id = request.args.get('sous_category_id', type=int)
        etat = request.args.get('etat', type=str)
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        sort = request.args.get('sort', type=str, default='latest')

        query = Produit.query

        if search:
            query = query.filter(Produit.name.ilike(f'%{search}%'))
        if category_id:
            query = query.filter(Produit.category_id == category_id)
        if sous_category_id:
            query = query.filter(Produit.sous_category_id == sous_category_id)
        if etat:
            query = query.filter(Produit.etat == etat)

        # Apply sorting
        if sort == 'price_asc':
            query = query.outerjoin(DureeAvecStock).order_by(
                case(
                    (DureeAvecStock.prix_1.is_(None), 1),
                    else_=0
                ).desc(),  # NULLs last
                DureeAvecStock.prix_1.asc(),
                Produit.id.asc()  # Secondary sort for stability
            )
        elif sort == 'price_desc':
            query = query.outerjoin(DureeAvecStock).order_by(
                case(
                    (DureeAvecStock.prix_1.is_(None), 1),
                    else_=0
                ).asc(),  # NULLs first
                DureeAvecStock.prix_1.desc(),
                Produit.id.asc()  # Secondary sort for stability
            )
        else:  # latest
            query = query.order_by(Produit.id.desc())

        # Log the query for debugging
        print("SQL Query:", str(query))

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        products = paginated.items

        # Log results for debugging
        result = []
        for product in products:
            product_data = product.to_dict()
            product_data["duree_avec_stock"] = [d.to_dict() for d in product.duree_avec_stock]
            result.append(product_data)
        print("Products:", [
            {
                "id": p["id"],
                "name": p["name"],
                "prix_1": p["duree_avec_stock"][0]["prix_1"] if p["duree_avec_stock"] else None
            } for p in result
        ])

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "records": result
        }), 200
    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500

@products_bp.route('/get_products_by_sous_category/<int:sous_category_id>', methods=['GET'])
def get_products_by_sous_category(sous_category_id):
    """Retrieve products by sous-category ID with pagination, optional search, and sorting."""
    try:
        sous_category = SousCategory.query.get(sous_category_id)
        if not sous_category:
            return jsonify({"message": "Sous-category not found"}), 404

        search = request.args.get('search', type=str, default="").strip()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        sort = request.args.get('sort', type=str, default='latest')

        query = Produit.query.filter(Produit.sous_category_id == sous_category_id)

        if search:
            query = query.filter(Produit.name.ilike(f'%{search}%'))

        # Apply sorting
        if sort == 'price_asc':
            query = query.outerjoin(DureeAvecStock).order_by(
                case(
                    (DureeAvecStock.prix_1.is_(None), 1),
                    else_=0
                ).desc(),  # NULLs last
                DureeAvecStock.prix_1.asc(),
                Produit.id.asc()  # Secondary sort for stability
            )
        elif sort == 'price_desc':
            query = query.outerjoin(DureeAvecStock).order_by(
                case(
                    (DureeAvecStock.prix_1.is_(None), 1),
                    else_=0
                ).asc(),  # NULLs first
                DureeAvecStock.prix_1.desc(),
                Produit.id.asc()  # Secondary sort for stability
            )
        else:  # latest
            query = query.order_by(Produit.id.desc())

        # Log the query for debugging
        print("SQL Query:", str(query))

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        products = paginated.items

        # Log results for debugging
        result = []
        for product in products:
            product_data = product.to_dict()
            product_data["duree_avec_stock"] = [d.to_dict() for d in product.duree_avec_stock]
            result.append(product_data)
        print("Products:", [
            {
                "id": p["id"],
                "name": p["name"],
                "prix_1": p["duree_avec_stock"][0]["prix_1"] if p["duree_avec_stock"] else None
            } for p in result
        ])

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "records": result
        }), 200
    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500

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