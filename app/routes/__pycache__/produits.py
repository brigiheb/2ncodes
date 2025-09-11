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
from sqlalchemy import case,or_
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models.user import User
from ..models.gest_prix import GestPrix
from sqlalchemy import func, case

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
        type_value = request.form.get('type')
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
            etat_commande=etat_commande,
            type=type_value
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
        # Query parameters
        search = request.args.get('search', type=str, default="").strip()
        category_id = request.args.get('category_id', type=int)
        sous_category_id = request.args.get('sous_category_id', type=int)
        etat = request.args.get('etat', type=str)
        etat_commande = request.args.get('etat_commande', type=str)
        photo_filter = request.args.get('photo', type=str)  # 'with_photo' or 'without_photo'
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        sort = request.args.get('sort', type=str, default='latest')

        query = Produit.query

        # Apply filters
        if search:
            query = query.filter(Produit.name.ilike(f'%{search}%'))
        if category_id:
            query = query.filter(Produit.category_id == category_id)
        if sous_category_id:
            query = query.filter(Produit.sous_category_id == sous_category_id)
        if etat:
            query = query.filter(Produit.etat == etat)
        if etat_commande:
            query = query.filter(Produit.etat_commande == etat_commande)
        if photo_filter:
            if photo_filter == 'with_photo':
                query = query.filter(Produit.photo.isnot(None))
            elif photo_filter == 'without_photo':
                query = query.filter(Produit.photo.is_(None))

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
        elif sort == 'name_asc':
            query = query.order_by(Produit.name.asc(), Produit.id.asc())
        elif sort == 'name_desc':
            query = query.order_by(Produit.name.desc(), Produit.id.asc())
        else:  # latest
            query = query.order_by(Produit.id.desc())

        # Log the query for debugging
        print("SQL Query:", str(query))

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        products = paginated.items

        # Prepare response
        result = []
        for product in products:
            product_data = product.to_dict()
            product_data["duree_avec_stock"] = [d.to_dict() for d in product.duree_avec_stock]
            result.append(product_data)

        # Log results for debugging
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
    


def _normalize(s: str) -> str:
    return (s or "").strip().lower()

def _prix_achat_for_admin_niveau(das, admin: User) -> float:
    niveau = (admin.niveau or 'niveau1').lower()
    if niveau == 'niveau2':
        return float(das.prix_2)
    if niveau == 'niveau3':
        return float(das.prix_3)
    return float(das.prix_1)

@products_bp.route('/get_products_by_sous_category/<int:sous_category_id>', methods=['GET'])
@jwt_required()
def get_products_by_sous_category(sous_category_id):
    """
    Admin: shows full duree_avec_stock + prix_affiche = prix_achat by admin niveau.
    Revendeur: shows ONLY (duree, quantite?, prix_affiche) per entry:
        prix_affiche = admin's GestPrix.prix_vente if set,
                       else admin's GestPrix.prix_achat,
                       else admin's prix_achat by niveau (fallback).
    If a product has no DureeAvecStock with stock, fall back to DureeSansStock.
    """
    try:
        caller_id = get_jwt_identity()
        caller = User.query.get(caller_id)
        if not caller or caller.role not in ('admin', 'revendeur'):
            return jsonify({"error": "Access denied. Only admin or revendeur."}), 403

        # resolve responsible admin (pricing owner)
        if caller.role == 'admin':
            pricing_admin = caller
        else:
            if not caller.responsable:
                return jsonify({"error": "Revendeur has no responsible admin assigned."}), 400
            pricing_admin = User.query.get(caller.responsable)
            if not pricing_admin or pricing_admin.role != 'admin':
                return jsonify({"error": "Responsible admin not found or invalid."}), 400

        sous_category = SousCategory.query.get(sous_category_id)
        if not sous_category:
            return jsonify({"message": "Sous-category not found"}), 404

        search = request.args.get('search', type=str, default="").strip()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        sort = request.args.get('sort', type=str, default='latest')

        # Base query: active products in sous_category
        query = Produit.query.filter(
            Produit.sous_category_id == sous_category_id,
            Produit.etat == 'actif'
        )

        if search:
            query = query.filter(Produit.name.ilike(f'%{search}%'))

        # Keep your existing sort behavior (based on DureeAvecStock.prix_1); sans-stock items will follow
        if sort == 'price_asc':
            query = query.outerjoin(DureeAvecStock).order_by(
                case((DureeAvecStock.prix_1.is_(None), 1), else_=0).desc(),
                DureeAvecStock.prix_1.asc(),
                Produit.id.asc()
            )
        elif sort == 'price_desc':
            query = query.outerjoin(DureeAvecStock).order_by(
                case((DureeAvecStock.prix_1.is_(None), 1), else_=0).asc(),
                DureeAvecStock.prix_1.desc(),
                Produit.id.asc()
            )
        else:
            query = query.order_by(Produit.id.desc())

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        products = paginated.items

        # Preload GestPrix for mapping: (produit_name_lower, duree_lower) -> (prix_vente, prix_achat_snapshot)
        gp_rows = GestPrix.query.all()
        gp_map = {
            (_normalize(gp.produit_name), _normalize(gp.duree)): (gp.prix_vente, gp.prix_achat)
            for gp in gp_rows
        }

        result = []
        for product in products:
            pdata = product.to_dict()

            # First try duree_avec_stock with quantite > 0
            das_list = [d for d in product.duree_avec_stock if (d.quantite or 0) > 0]

            if das_list:
                if caller.role == 'admin':
                    das_entries = []
                    for d in das_list:
                        prix_achat = _prix_achat_for_admin_niveau(d, pricing_admin)
                        d_full = d.to_dict()
                        d_full["prix_affiche"] = prix_achat
                        das_entries.append(d_full)
                    pdata["duree_avec_stock"] = das_entries
                else:
                    das_entries = []
                    for d in das_list:
                        key = (_normalize(product.name or ""), _normalize(d.duree))
                        prix_vente, prix_achat_gp = gp_map.get(key, (None, None))

                        if prix_vente and float(prix_vente) > 0:
                            prix_affiche = float(prix_vente)
                        elif prix_achat_gp is not None:
                            prix_affiche = float(prix_achat_gp)
                        else:
                            prix_affiche = _prix_achat_for_admin_niveau(d, pricing_admin)

                        das_entries.append({
                            "duree": d.duree,
                            "Quantite": d.quantite,
                            "prix_affiche": prix_affiche
                        })
                    pdata = {
                        "id": product.id,
                        "name": product.name,
                        "photo": product.photo,
                        "sous_category_id": product.sous_category_id,
                        "etat": product.etat,
                        "type": product.type,
                        "duree_avec_stock": das_entries
                    }

            else:
                # Fallback: use duree_sans_stock (only if active entries exist)
                dss_list = [d for d in product.duree_sans_stock if d.etat == 'actif']
                if not dss_list:
                    # No DAS with stock and no DSS → skip this product
                    continue

                if caller.role == 'admin':
                    dss_entries = []
                    for d in dss_list:
                        prix_achat = _prix_achat_for_admin_niveau(d, pricing_admin)
                        d_full = d.to_dict()  # contains prix_1/2/3 for admin
                        d_full["prix_affiche"] = prix_achat
                        # for UI consistency, add Quantite=None
                        d_full["Quantite"] = None
                        dss_entries.append(d_full)
                    # Put them under the same key; front-end can check Quantite None
                    pdata["duree_avec_stock"] = dss_entries
                else:
                    dss_entries = []
                    for d in dss_list:
                        key = (_normalize(product.name or ""), _normalize(d.duree))
                        prix_vente, prix_achat_gp = gp_map.get(key, (None, None))

                        if prix_vente and float(prix_vente) > 0:
                            prix_affiche = float(prix_vente)
                        elif prix_achat_gp is not None:
                            prix_affiche = float(prix_achat_gp)
                        else:
                            prix_affiche = _prix_achat_for_admin_niveau(d, pricing_admin)

                        dss_entries.append({
                            "duree": d.duree,
                            "Quantite": None,  # no stock quantity in DSS
                            "prix_affiche": prix_affiche
                        })

                    pdata = {
                        "id": product.id,
                        "name": product.name,
                        "photo": product.photo,
                        "sous_category_id": product.sous_category_id,
                        "etat": product.etat,
                        "type": product.type,
                        "duree_avec_stock": dss_entries  # reuse same key for client
                    }

            result.append(pdata)

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
        type_value = request.form.get('type')
        photo_file = request.files.get('photo')

        product.name = name or product.name
        product.category_id = category_id or product.category_id
        product.sous_category_id = sous_category_id or product.sous_category_id
        product.etat = etat or product.etat
        product.affichage = affichage or product.affichage
        product.etat_commande = etat_commande or product.etat_commande
        product.type = type_value or product.type

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

        # Delete associated image if it exists
        if product.photo:
            photo_path = os.path.join(current_app.root_path, product.photo)
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except Exception as e:
                    print(f"[WARNING] Failed to delete photo: {e}")

        # Delete related DureeAvecStock entries
        from ..models.duree_avec_stock import DureeAvecStock  # adjust if already imported globally
        durees = DureeAvecStock.query.filter_by(produit_id=product.id).all()
        for d in durees:
            db.session.delete(d)

        db.session.delete(product)
        db.session.commit()

        return jsonify({"message": "Product and related stock entries deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    

@products_bp.route('/get_filter_options', methods=['GET'])
def get_filter_options():
    """Retrieve filter options for products including categories, sous-categories, and etat_commande."""
    try:
        # Fetch categories
        categories = Category.query.order_by(Category.nom.asc()).all()
        category_options = [{"id": c.id, "name": c.nom} for c in categories]

        # Fetch sous-categories
        sous_categories = SousCategory.query.order_by(SousCategory.name.asc()).all()
        sous_category_options = [{"id": sc.id, "name": sc.name, "category_id": sc.category_id} for sc in sous_categories]

        # Fetch distinct etat_commande values
        etat_commande_options = db.session.query(Produit.etat_commande).distinct().order_by(Produit.etat_commande.asc()).all()
        etat_commande_options = [e.etat_commande for e in etat_commande_options if e.etat_commande]

        # Fetch distinct names (optional, for autocomplete-like functionality)
        name_options = db.session.query(Produit.name).distinct().order_by(Produit.name.asc()).all()
        name_options = [n.name for n in name_options if n.name]

        # Determine if products have photos (True if at least one product has a photo)
        has_photos = db.session.query(Produit).filter(Produit.photo.isnot(None)).count() > 0
        photo_options = ['with_photo', 'without_photo'] if has_photos else []

        return jsonify({
            "categories": category_options,
            "sous_categories": sous_category_options,
            "etat_commande": etat_commande_options,
            "names": name_options,
        }), 200
    except Exception as e:
        print("Error in get_filter_options:", str(e))
        return jsonify({"error": str(e)}), 500

        