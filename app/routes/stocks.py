# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.stock import Stock
from ..models.product import Produit

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route('/get_stocks', methods=['GET'])
def get_all_stocks():
    """Get all stocks with pagination, search """
    try:
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = 20

        query = db.session.query(Stock).join(Produit)

        if search_query:
            query = query.filter(
                db.or_(
                    Produit.name.ilike(f"%{search_query}%"),
                    Stock.fournisseur.ilike(f"%{search_query}%"),
                    Stock.code.ilike(f"%{search_query}%"),
                    Stock.note.ilike(f"%{search_query}%"),
                    Stock.duree.ilike(f"%{search_query}%"),
                    Stock.prix_achat.ilike(f"%{search_query}%")
                )
            )


        paginated = query.order_by(Stock.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        stocks = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "stocks": [stock.to_dict() for stock in stocks]
        }), 200
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@stocks_bp.route('/get_stock/<int:stock_id>', methods=['GET'])
def get_stock(stock_id):
    """Get a single stock by ID."""
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": f"Stock with id {stock_id} not found"}), 404
    return jsonify(stock.to_dict()), 200

@stocks_bp.route('/add_stock', methods=['POST'])
def add_stock():
    """Add a new stock with an automatic date_ajout."""
    data = request.get_json()
    produit_id = data.get('produit_id')
    fournisseur = data.get('fournisseur')
    prix_achat = data.get('prix_achat')
    duree = data.get('duree')
    code = data.get('code')
    note = data.get('note', None)  # ✅ Optional note

    # Check if produit exists
    produit = Produit.query.get(produit_id)
    if not produit:
        return jsonify({"error": f"Produit with id {produit_id} not found"}), 404

    # Create and add new stock (date_ajout auto-set)
    new_stock = Stock(
        produit_id=produit_id,
        fournisseur=fournisseur,
        prix_achat=prix_achat,
        duree=duree,
        code=code,
        note=note
    )
    db.session.add(new_stock)
    db.session.commit()

    return jsonify(new_stock.to_dict()), 201

@stocks_bp.route('/put_stock/<int:stock_id>', methods=['PUT'])
def update_stock(stock_id):
    """Update an existing stock."""
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": f"Stock with id {stock_id} not found"}), 404

    data = request.get_json()
    
    # Update produit_id if provided and valid
    produit_id = data.get('produit_id')
    if produit_id:
        produit = Produit.query.get(produit_id)
        if not produit:
            return jsonify({"error": f"Produit with id {produit_id} not found"}), 404
        stock.produit_id = produit_id

    stock.fournisseur = data.get('fournisseur', stock.fournisseur)
    stock.prix_achat = data.get('prix_achat', stock.prix_achat)
    stock.duree = data.get('duree', stock.duree)
    stock.code = data.get('code', stock.code)
    stock.note = data.get('note', stock.note)

    db.session.commit()
    return jsonify(stock.to_dict()), 200

@stocks_bp.route('/del_stock/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    """Delete a stock."""
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": f"Stock with id {stock_id} not found"}), 404

    db.session.delete(stock)
    db.session.commit()

    return jsonify({"message": f"Stock with id {stock_id} has been deleted"}), 200
