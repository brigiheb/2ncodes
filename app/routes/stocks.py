# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.stock import Stock
from ..models.product import Produit
from ..models.duree_avec_stock import DureeAvecStock

stocks_bp = Blueprint('stocks', __name__)

# ✅ Normalized Matching Helper
def update_duree_avec_stock(produit_id, duree):
    """Update quantite and moyenne in DureeAvecStock if matching entry exists."""
    if not duree:
        return
    normalized_duree = duree.strip().lower()

    entry = DureeAvecStock.query.filter(
        DureeAvecStock.produit_id == produit_id,
        db.func.lower(db.func.trim(DureeAvecStock.duree)) == normalized_duree
    ).first()

    if entry:
        entry.update_quantite()
        entry.update_moyenne()
        db.session.commit()

@stocks_bp.route('/get_stocks', methods=['GET'])
def get_all_stocks():
    """Retrieve all stocks with pagination, filtering, and sorting."""
    try:
        # Query parameters
        search_query = request.args.get('search', type=str, default="").strip().lower()
        produit_name = request.args.get('produit_name', type=str, default="").strip().lower()
        fournisseur = request.args.get('fournisseur', type=str, default="").strip().lower()
        duree = request.args.get('duree', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        sort = request.args.get('sort', type=str, default='latest')

        query = db.session.query(Stock).join(Produit)

        # Apply filters
        if search_query:
            query = query.filter(
                db.or_(
                    Produit.name.ilike(f"%{search_query}%"),
                    Stock.fournisseur.ilike(f"%{search_query}%"),
                    Stock.code.ilike(f"%{search_query}%"),
                    Stock.note.ilike(f"%{search_query}%"),
                    Stock.duree.ilike(f"%{search_query}%"),
                    db.cast(Stock.prix_achat, db.String).ilike(f"%{search_query}%")
                )
            )
        if produit_name:
            query = query.filter(Produit.name.ilike(f"%{produit_name}%"))
        if fournisseur:
            query = query.filter(Stock.fournisseur.ilike(f"%{fournisseur}%"))
        if duree:
            query = query.filter(Stock.duree.ilike(f"%{duree}%"))

        # Apply sorting
        if sort == 'prix_achat_asc':
            query = query.order_by(Stock.prix_achat.asc(), Stock.id.asc())
        elif sort == 'prix_achat_desc':
            query = query.order_by(Stock.prix_achat.desc(), Stock.id.asc())
        elif sort == 'produit_name_asc':
            query = query.order_by(Produit.name.asc(), Stock.id.asc())
        elif sort == 'produit_name_desc':
            query = query.order_by(Produit.name.desc(), Stock.id.asc())
        else:  # latest
            query = query.order_by(Stock.id.desc())

        # Log the query for debugging
        print("SQL Query:", str(query))

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        stocks = paginated.items

        # Log results for debugging
        print("Stocks:", [
            {
                "id": stock.id,
                "produit_name": stock.produit.name if stock.produit else None,
                "fournisseur": stock.fournisseur,
                "duree": stock.duree,
                "prix_achat": stock.prix_achat
            } for stock in stocks
        ])

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "stocks": [stock.to_dict() for stock in stocks]
        }), 200
    except Exception as e:
        print("Error in get_all_stocks:", str(e))
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    
@stocks_bp.route('/get_stock/<int:stock_id>', methods=['GET'])
def get_stock(stock_id):
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": f"Stock with id {stock_id} not found"}), 404
    return jsonify(stock.to_dict()), 200

@stocks_bp.route('/add_stock', methods=['POST'])
def add_stock():
    try:
        data = request.get_json()
        produit_id = data.get('produit_id')
        fournisseur = data.get('fournisseur', '').strip()
        prix_achat = data.get('prix_achat')
        duree = data.get('duree', '').strip()
        codes = data.get('codes')  # Expecting an array of codes
        note = data.get('note', None)

        # Validate required fields
        if not all([produit_id, prix_achat is not None, duree, codes]):
            return jsonify({"error": "Missing required fields (produit_id, prix_achat, duree, or codes)"}), 400

        # Validate produit_id
        produit = Produit.query.get(produit_id)
        if not produit:
            print(f"Error: Produit with id {produit_id} not found")
            return jsonify({"error": f"Produit with id {produit_id} not found"}), 404

        # Validate codes
        if not isinstance(codes, list) or not codes:
            print("Error: Codes must be a non-empty array")
            return jsonify({"error": "Codes must be a non-empty array"}), 400

        # Check for duplicate codes in the input
        code_set = set(code.strip().lower() for code in codes if code and isinstance(code, str))
        if len(code_set) < len([code for code in codes if code and isinstance(code, str)]):
            print("Error: Duplicate codes found in input")
            return jsonify({"error": "Duplicate codes are not allowed"}), 400

        # Check for existing codes in the database
        existing_codes = db.session.query(Stock.code).filter(
            Stock.code.in_([code.strip() for code in codes if code and isinstance(code, str)])
        ).all()
        existing_codes = {code[0].lower() for code in existing_codes}
        if existing_codes.intersection(code_set):
            print(f"Error: Codes already exist in database: {existing_codes.intersection(code_set)}")
            return jsonify({"error": f"Codes already exist in database: {', '.join(existing_codes.intersection(code_set))}"}), 400

        # Normalize inputs
        normalized_fournisseur = fournisseur.lower()
        normalized_duree = duree.lower()
        prix_achat = float(prix_achat)  # Convert to float to handle integer inputs

        # Create stock entries for each code
        new_stocks = []
        for code in codes:
            if not code or not isinstance(code, str):
                print(f"Warning: Skipping invalid code: {code}")
                continue  # Skip invalid codes
            new_stock = Stock(
                produit_id=produit_id,
                fournisseur=normalized_fournisseur,
                prix_achat=prix_achat,
                duree=normalized_duree,
                code=code.strip(),
                note=note
            )
            db.session.add(new_stock)
            new_stocks.append(new_stock)

        # Single commit for all stock entries
        db.session.commit()

        # Update DureeAvecStock once for all entries
        try:
            update_duree_avec_stock(produit_id, normalized_duree)
        except Exception as e:
            print(f"Error updating DureeAvecStock: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Failed to update DureeAvecStock", "details": str(e)}), 500

        return jsonify([stock.to_dict() for stock in new_stocks]), 201

    except Exception as e:
        print(f"Error in add_stock: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    
@stocks_bp.route('/put_stock/<int:stock_id>', methods=['PUT'])
def update_stock(stock_id):
    try:
        stock = Stock.query.get(stock_id)
        if not stock:
            return jsonify({"error": f"Stock with id {stock_id} not found"}), 404

        original_duree = stock.duree
        original_fournisseur = stock.fournisseur
        original_produit_id = stock.produit_id

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Check for duplicate code
        new_code = data.get('code', stock.code)
        if new_code and new_code.strip():
            normalized_code = new_code.strip().lower()
            existing_code = db.session.query(Stock.code).filter(
                Stock.code.ilike(normalized_code),
                Stock.id != stock_id  # Exclude the current stock
            ).first()
            if existing_code:
                print(f"Error: Code already exists in database: {normalized_code}")
                return jsonify({"error": f"Code already exists in database: {normalized_code}"}), 400

        # Validate produit_id if provided
        produit_id = data.get('produit_id')
        if produit_id:
            produit = Produit.query.get(produit_id)
            if not produit:
                return jsonify({"error": f"Produit with id {produit_id} not found"}), 404
            stock.produit_id = produit_id

        # Update stock fields
        stock.fournisseur = data.get('fournisseur', stock.fournisseur).strip().lower()
        stock.prix_achat = data.get('prix_achat', stock.prix_achat)
        stock.duree = data.get('duree', stock.duree).strip().lower()
        stock.code = new_code.strip() if new_code else stock.code
        stock.note = data.get('note', stock.note)

        db.session.commit()

        # Update both old and new DureeAvecStock relations
        try:
            update_duree_avec_stock(original_produit_id, original_duree)
            update_duree_avec_stock(stock.produit_id, stock.duree)
        except Exception as e:
            print(f"Error updating DureeAvecStock: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Failed to update DureeAvecStock", "details": str(e)}), 500

        return jsonify(stock.to_dict()), 200
    except Exception as e:
        print(f"Error in update_stock: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    
@stocks_bp.route('/del_stock/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    stock = Stock.query.get(stock_id)
    if not stock:
        return jsonify({"error": f"Stock with id {stock_id} not found"}), 404

    produit_id = stock.produit_id
    duree = stock.duree

    db.session.delete(stock)
    db.session.commit()

    # Update DureeAvecStock after deletion (only match produit_id and duree)
    update_duree_avec_stock(produit_id, duree)

    return jsonify({"message": f"Stock with id {stock_id} has been deleted"}), 200

@stocks_bp.route('/get_filter_options', methods=['GET'])
def get_filter_options():
    """Retrieve filter options for stocks including produit_name, fournisseur, and duree."""
    try:
        # Fetch distinct product names
        produit_names = db.session.query(Produit.name).distinct().order_by(Produit.name.asc()).all()
        produit_name_options = [name[0] for name in produit_names if name[0]]

        # Fetch distinct fournisseurs
        fournisseurs = db.session.query(Stock.fournisseur).distinct().order_by(Stock.fournisseur.asc()).all()
        fournisseur_options = [fournisseur[0] for fournisseur in fournisseurs if fournisseur[0]]

        # Fetch distinct durees
        durees = db.session.query(Stock.duree).distinct().order_by(Stock.duree.asc()).all()
        duree_options = [duree[0] for duree in durees if duree[0]]

        return jsonify({
            "produit_names": produit_name_options,
            "fournisseurs": fournisseur_options,
            "durees": duree_options
        }), 200
    except Exception as e:
        print("Error in get_filter_options:", str(e))
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500