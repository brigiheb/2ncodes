# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.duree_sans_stock import DureeSansStock
from ..models.product import Produit
from datetime import datetime
from sqlalchemy import func, cast, String, or_

duree_sans_stock_bp = Blueprint('duree_sans_stock', __name__)

@duree_sans_stock_bp.route('/get_dureeSansStock', methods=['GET'])
def get_all_duree_sans_stock():
    """Get all duree_sans_stock entries with pagination, filters, and search."""
    try:
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        search_query = request.args.get('search', type=str, default="").strip().lower()
        produit_id = request.args.get('produit_id', type=int, default=None)
        duree = request.args.get('duree', type=str, default="").strip().lower()
        etat = request.args.get('etat', type=str, default="").strip().lower()
        fournisseur = request.args.get('fournisseur', type=str, default="").strip().lower()

        query = DureeSansStock.query.join(Produit, DureeSansStock.produit_id == Produit.id)

        if search_query:
            query = query.filter(
                or_(
                    Produit.name.ilike(f"%{search_query}%"),
                    DureeSansStock.duree.ilike(f"%{search_query}%"),
                    DureeSansStock.fournisseur.ilike(f"%{search_query}%"),
                    cast(DureeSansStock.prix_1, String).ilike(f"%{search_query}%"),
                    cast(DureeSansStock.prix_2, String).ilike(f"%{search_query}%"),
                    cast(DureeSansStock.prix_3, String).ilike(f"%{search_query}%"),
                    cast(DureeSansStock.note, String).ilike(f"%{search_query}%"),
                    DureeSansStock.etat.ilike(f"%{search_query}%"),
                    cast(DureeSansStock.date_ajout, String).ilike(f"%{search_query}%")
                )
            )

        if produit_id is not None:
            query = query.filter(DureeSansStock.produit_id == produit_id)
        if duree:
            query = query.filter(func.lower(func.trim(DureeSansStock.duree)) == duree)
        if etat:
            query = query.filter(DureeSansStock.etat.ilike(etat))
        if fournisseur:
            query = query.filter(func.lower(func.trim(DureeSansStock.fournisseur)) == fournisseur)

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

@duree_sans_stock_bp.route('/get_filter_options', methods=['GET'])
def get_filter_options():
    """Fetch unique produit names with IDs, duree, and fournisseur values for filtering."""
    try:
        produits = (
            db.session.query(Produit.id, Produit.name.label('produit_name'))
            .join(DureeSansStock, DureeSansStock.produit_id == Produit.id)
            .distinct()
            .order_by(Produit.name.asc())
            .all()
        )

        durees = (
            db.session.query(func.lower(func.trim(DureeSansStock.duree)).label('duree'))
            .distinct()
            .order_by(func.lower(func.trim(DureeSansStock.duree)).asc())
            .all()
        )

        fournisseurs = (
            db.session.query(func.lower(func.trim(DureeSansStock.fournisseur)).label('fournisseur'))
            .distinct()
            .order_by(func.lower(func.trim(DureeSansStock.fournisseur)).asc())
            .all()
        )

        response = {
            "produits": [{"id": p.id, "produit_name": p.produit_name} for p in produits],
            "durees": [d.duree for d in durees if d.duree],
            "fournisseurs": [f.fournisseur for f in fournisseurs if f.fournisseur]
        }

        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch filter options", "details": str(e)}), 500