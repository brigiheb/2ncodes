# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.duree_sans_stock import DureeSansStock
from ..models.product import Produit
from datetime import datetime

duree_sans_stock_bp = Blueprint('duree_sans_stock', __name__)

@duree_sans_stock_bp.route('/get_dureeSansStock', methods=['GET'])
def get_all_duree_sans_stock():
    """Get all duree_sans_stock entries with pagination and optional etat filter."""
    try:
        search_query = request.args.get('search', type=str, default=None)
        etat = request.args.get('etat', type=str, default=None)
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)

        query = DureeSansStock.query.join(Produit, DureeSansStock.produit_id == Produit.id)

        # Apply search filter only if search_query is provided
        if search_query and search_query.strip():
            search_query = search_query.strip().lower()
            query = query.filter(
                db.or_(
                    Produit.name.ilike(f"%{search_query}%"),  # Filter on Produit's name
                    DureeSansStock.fournisseur.ilike(f"%{search_query}%"),
                    DureeSansStock.etat.ilike(f"%{search_query}%"),
                    DureeSansStock.duree.ilike(f"%{search_query}%"),
                    db.cast(DureeSansStock.note, db.String).ilike(f"%{search_query}%")
                )
            )

        # Apply etat filter only if etat is provided
        if etat and etat.strip():
            etat = etat.strip().lower()
            query = query.filter(DureeSansStock.etat == etat)

        # Apply pagination
        paginated = query.order_by(DureeSansStock.id.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        results = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "records": [record.to_dict() for record in results]
        }), 200
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@duree_sans_stock_bp.route('/get_dureeSansStock/<int:record_id>', methods=['GET'])
def get_duree_sans_stock(record_id):
    """Get a single duree_sans_stock entry by ID."""
    record = DureeSansStock.query.get(record_id)
    if not record:
        return jsonify({"error": f"Record with id {record_id} not found"}), 404
    return jsonify(record.to_dict()), 200

@duree_sans_stock_bp.route('/add_dureeSansStock', methods=['POST'])
def add_duree_sans_stock():
    """Add a new duree_sans_stock entry."""
    data = request.get_json()
    produit_id = data.get('produit_id')
    duree = data.get('duree')
    fournisseur = data.get('fournisseur')
    note = data.get('note')
    prix_1 = data.get('prix_1')
    prix_2 = data.get('prix_2')
    prix_3 = data.get('prix_3')
    etat = data.get('etat', 'actif')

    # Check if produit exists
    produit = Produit.query.get(produit_id)
    if not produit:
        return jsonify({"error": f"Produit with id {produit_id} not found"}), 404

    # Create and add new record
    new_record = DureeSansStock(
        produit_id=produit_id,
        duree=duree,
        fournisseur=fournisseur,
        note=note,
        prix_1=prix_1,
        prix_2=prix_2,
        prix_3=prix_3,
        etat=etat,
        date_ajout=datetime.utcnow()
    )
    db.session.add(new_record)
    db.session.commit()

    return jsonify(new_record.to_dict()), 201

@duree_sans_stock_bp.route('/put_dureeSansStock/<int:record_id>', methods=['PUT'])
def update_duree_sans_stock(record_id):
    """Update an existing duree_sans_stock entry."""
    record = DureeSansStock.query.get(record_id)
    if not record:
        return jsonify({"error": f"Record with id {record_id} not found"}), 404

    data = request.get_json()

    # Update product if provided and exists
    produit_id = data.get('produit_id')
    if produit_id:
        produit = Produit.query.get(produit_id)
        if not produit:
            return jsonify({"error": f"Product with id {produit_id} not found"}), 404
        record.produit_id = produit_id

    record.duree = data.get('duree', record.duree)
    record.fournisseur = data.get('fournisseur', record.fournisseur)
    record.note = data.get('note', record.note)
    record.prix_1 = data.get('prix_1', record.prix_1)
    record.prix_2 = data.get('prix_2', record.prix_2)
    record.prix_3 = data.get('prix_3', record.prix_3)
    record.etat = data.get('etat', record.etat)

    db.session.commit()
    return jsonify(record.to_dict()), 200

@duree_sans_stock_bp.route('/del_dureeSansStock/<int:record_id>', methods=['DELETE'])
def delete_duree_sans_stock(record_id):
    """Delete a duree_sans_stock entry."""
    record = DureeSansStock.query.get(record_id)
    if not record:
        return jsonify({"error": f"Record with id {record_id} not found"}), 404

    db.session.delete(record)
    db.session.commit()

    return jsonify({"message": f"Record with id {record_id} has been deleted"}), 200