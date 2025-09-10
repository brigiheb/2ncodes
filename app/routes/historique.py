# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models.user import User
from ..models.product import Produit
from ..models.stock import Stock
from ..models.duree_avec_stock import DureeAvecStock
from ..models.historique import Historique
from sqlalchemy.sql import func
from ..routes.users import emit_user_updated  
from ..models.return_request import ReturnRequest


historique_bp = Blueprint('historique', __name__, url_prefix='/api/historique')


@historique_bp.route('/acheter', methods=['POST'])
@jwt_required()
def acheter_produit():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    if user.role not in ["admin", "revendeur"]:
        return jsonify({"error": "Seuls les admins et revendeurs peuvent acheter des produits"}), 403

    data = request.get_json()
    produit_id = data.get("produit_id")
    quantite = data.get("quantite")
    duree = data.get("duree")
    note = data.get("note", "")

    if not produit_id or not quantite or not duree:
        return jsonify({"error": "Veuillez fournir produit_id, quantite et duree"}), 400

    if not isinstance(quantite, int) or quantite <= 0:
        return jsonify({"error": "Quantité doit être un entier positif"}), 400

    produit = Produit.query.get(produit_id)
    if not produit:
        return jsonify({"error": "Produit introuvable"}), 404

    # Fetch matching DureeAvecStock entry
    duree_entry = DureeAvecStock.query.filter_by(produit_id=produit_id, duree=duree).first()
    if not duree_entry:
        return jsonify({"error": "Entrée DureeAvecStock non trouvée pour cette durée"}), 404

    # Check if DureeAvecStock quantite is sufficient
    if duree_entry.quantite < quantite:
        return jsonify({"error": f"Quantité insuffisante dans DureeAvecStock ({duree_entry.quantite} disponible)"}), 400

    # Fetch matching stock codes
    matching_codes = Stock.query.filter_by(produit_id=produit_id, duree=duree).limit(quantite).all()
    if len(matching_codes) < quantite:
        return jsonify({"error": f"Stock insuffisant ({len(matching_codes)} codes disponibles)"}), 400

    # Select price based on user niveau
    prix_unitaire = 0
    if user.niveau == "niveau1":
        prix_unitaire = duree_entry.prix_1
    elif user.niveau == "niveau2":
        prix_unitaire = duree_entry.prix_2
    else:
        prix_unitaire = duree_entry.prix_3

    total = prix_unitaire * quantite
    if user.solde < total:
        return jsonify({"error": f"Solde insuffisant ({user.solde} TND disponible)"}), 400

    # Extract codes
    codes_list = [s.code for s in matching_codes]
    codes_str = ", ".join(codes_list)

    try:
        # Remove used codes from Stock table
        for s in matching_codes:
            db.session.delete(s)

        # Update quantite in DureeAvecStock by subtracting purchased quantity
        duree_entry.quantite -= quantite

        # Deduct solde
        user.solde -= total

        # Save historique
        historique = Historique(
            user_id=user_id,
            produit=produit.name,
            duree=duree,
            codes=codes_str,
            montant=total,
            note=note
        )
        db.session.add(historique)
        db.session.commit()

        # Emit user_updated event for balance change
        emit_user_updated(user, exclude_user_id=user_id)

        return jsonify({
            "message": "Purchase successful",
            "produit_id": produit_id,
            "quantite": quantite,
            "duree": duree,
            "codes": codes_list,
            "montant": float(total),
            "new_solde": float(user.solde)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de l'achat: {str(e)}"}), 500

@historique_bp.route('/get', methods=['GET'])
@jwt_required()
def get_historique():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    search = request.args.get('search', '').lower()
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    user_nom = request.args.get('user_nom', '').lower()
    produit = request.args.get('produit', '').lower()
    duree = request.args.get('duree', '').lower()

    # Base query with join to User
    base_query = Historique.query.join(User, Historique.user_id == User.id)

    # Apply role-based filtering
    if user.role in ["manager", "admin_boss"]:
        # Manager sees all historiques
        pass
    elif user.role == "admin":
        # Admin sees their own historique + historiques of their revendeurs
        revendeur_ids = User.query.filter_by(responsable=user.id, role="revendeur")\
                                  .with_entities(User.id).all()
        revendeur_ids = [uid for (uid,) in revendeur_ids]
        relevant_ids = [user.id] + revendeur_ids
        base_query = base_query.filter(Historique.user_id.in_(relevant_ids))
    elif user.role == "revendeur":
        # Revendeur sees only their own historique
        base_query = base_query.filter(Historique.user_id == user.id)
    else:
        return jsonify({"error": "Unauthorized role"}), 403

    # Apply filters
    if user_nom:
        base_query = base_query.filter(User.nom.ilike(f"%{user_nom}%"))
    if produit:
        base_query = base_query.filter(Historique.produit.ilike(f"%{produit}%"))
    if duree:
        base_query = base_query.filter(Historique.duree.ilike(f"%{duree}%"))
    if search:
        base_query = base_query.filter(
            db.or_(
                Historique.produit.ilike(f"%{search}%"),
                User.nom.ilike(f"%{search}%"),
                func.cast(Historique.montant, db.String).ilike(f"%{search}%"),
                Historique.note.ilike(f"%{search}%")
            )
        )

    # Query 1: Fetch all Historique records with pending ReturnRequest
    pending_query = base_query.join(ReturnRequest, Historique.id == ReturnRequest.historique_id)\
                             .filter(ReturnRequest.status == 'pending')\
                             .order_by(Historique.date.desc())

    # Query 2: Fetch Historique records without pending ReturnRequest
    non_pending_query = base_query.outerjoin(ReturnRequest, Historique.id == ReturnRequest.historique_id)\
                                  .filter(db.or_(ReturnRequest.status != 'pending', ReturnRequest.status.is_(None)))\
                                  .order_by(Historique.date.desc())

    # Execute queries to fetch all matching records
    pending_items = pending_query.all()
    non_pending_items = non_pending_query.all()

    # Combine results: pending first, then non-pending
    all_items = pending_items + non_pending_items
    total = len(all_items)

    # Manually apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_items = all_items[start_idx:end_idx]

    # Process items for response
    items = []
    for h in paginated_items:
        h_dict = h.to_dict()
        # Fetch the latest ReturnRequest for this historique, if any
        return_request = ReturnRequest.query.filter_by(historique_id=h.id).order_by(ReturnRequest.created_at.desc()).first()
        h_dict['return_status'] = return_request.status if return_request else None
        h_dict['return_request_id'] = return_request.id if return_request else None
        h_dict['return_reason'] = return_request.reason if return_request else None
        items.append(h_dict)

    # Calculate total pages
    pages = (total + per_page - 1) // per_page if total > 0 else 1

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "historiques": items
    }), 200

@historique_bp.route('/get_my_history', methods=['GET'])
@jwt_required()
def get_my_history():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    search = request.args.get('search', '').lower()
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    user_nom = request.args.get('user_nom', '').lower()
    produit = request.args.get('produit', '').lower()
    duree = request.args.get('duree', '').lower()

    query = Historique.query.filter_by(user_id=user.id).join(User, Historique.user_id == User.id)

    # Apply filters
    if user_nom:
        query = query.filter(User.nom.ilike(f"%{user_nom}%"))
    if produit:
        query = query.filter(Historique.produit.ilike(f"%{produit}%"))
    if duree:
        query = query.filter(Historique.duree.ilike(f"%{duree}%"))

    # Apply search
    if search:
        query = query.filter(
            db.or_(
                Historique.produit.ilike(f"%{search}%"),
                User.nom.ilike(f"%{search}%"),
                func.cast(Historique.montant, db.String).ilike(f"%{search}%"),
                Historique.note.ilike(f"%{search}%")
            )
        )

    paginated = query.order_by(Historique.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for h in paginated.items:
        h_dict = h.to_dict()
        # Fetch the latest ReturnRequest for this historique, if any
        return_request = ReturnRequest.query.filter_by(historique_id=h.id).order_by(ReturnRequest.created_at.desc()).first()
        h_dict['return_status'] = return_request.status if return_request else None
        h_dict['return_request_id'] = return_request.id if return_request else None
        h_dict['return_reason'] = return_request.reason if return_request else None  # Add return reason
        items.append(h_dict)

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "historiques": items
    }), 200

@historique_bp.route('/get_filter_options', methods=['GET'])
@jwt_required()
def get_filter_options():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        # Base query for filter options
        query = Historique.query.join(User, Historique.user_id == User.id)

        if user.role in ["manager", "admin_boss"]:
            # Manager sees all historiques
            pass
        elif user.role == "admin":
            # Admin sees their own + revendeurs' historiques
            revendeur_ids = User.query.filter_by(responsable=user.id, role="revendeur")\
                                      .with_entities(User.id).all()
            revendeur_ids = [uid for (uid,) in revendeur_ids]
            relevant_ids = [user.id] + revendeur_ids
            query = query.filter(Historique.user_id.in_(relevant_ids))
        elif user.role == "revendeur":
            # Revendeur sees only their own historique
            query = query.filter(Historique.user_id == user.id)
        else:
            return jsonify({"error": "Unauthorized role"}), 403

        # Fetch distinct values
        user_noms = query.with_entities(User.nom).distinct().all()
        produits = query.with_entities(Historique.produit).distinct().all()
        durees = query.with_entities(Historique.duree).distinct().all()

        return jsonify({
            "user_noms": [nom[0] for nom in user_noms if nom[0]],
            "produits": [produit[0] for produit in produits if produit[0]],
            "durees": [duree[0] for duree in durees if duree[0]]
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@historique_bp.route('/get_revendeurs', methods=['GET'])
@jwt_required()
def get_revendeurs():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role != "admin":
        return jsonify({"error": "Unauthorized: Only admins can access revendeurs"}), 403

    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    search = request.args.get('search', '').lower()

    query = User.query.filter_by(responsable=user.id, role="revendeur")

    if search:
        query = query.filter(
            db.or_(
                User.nom.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    paginated = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    revendeurs = [r.to_dict() for r in paginated.items]

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "revendeurs": revendeurs
    }), 200


@historique_bp.route('/<int:order_id>/return', methods=['POST'])
@jwt_required()
def request_return(order_id):
    """
    Admin/Revendeur: create a return request with a reason.
    Manager later approves/rejects via /returns/<req_id>/approve or /reject.
    """
    user_id = get_jwt_identity()
    current_user = User.query.get(user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    if current_user.role not in ["admin", "revendeur"]:
        return jsonify({"error": "Only admins/revendeurs can request returns"}), 403

    data = request.get_json() or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "Reason is required"}), 400

    historique = Historique.query.get(order_id)
    if not historique:
        return jsonify({"error": "Order not found"}), 404

    # Revendeur can only request a return for their own order
    if current_user.role == "revendeur" and historique.user_id != current_user.id:
        return jsonify({"error": "You can only request returns for your own orders"}), 403

    # Prevent duplicate pending requests
    existing = ReturnRequest.query.filter_by(historique_id=order_id, status="pending").first()
    if existing:
        return jsonify({"error": "A pending return request already exists for this order"}), 400

    rr = ReturnRequest(historique_id=order_id, requester_id=current_user.id, reason=reason)
    db.session.add(rr)
    db.session.commit()

    return jsonify({
        "message": "Return request submitted",
        "request_id": rr.id
    }), 201

@historique_bp.route('/returns/<int:req_id>/approve', methods=['POST'])
@jwt_required()
def approve_return(req_id):
    reviewer_id = get_jwt_identity()
    reviewer = User.query.get(reviewer_id)
    if not reviewer:
        return jsonify({"error": "User not found"}), 404
    if reviewer.role not in ["manager", "admin_boss"]:
        return jsonify({"error": "Only manager/admin_boss can approve returns"}), 403

    rr = ReturnRequest.query.get(req_id)

    h = Historique.query.get(rr.historique_id)
    if not h:
        return jsonify({"error": "Original order not found"}), 404

    try:
        # Cache before mutations/deletes
        total = float(h.montant)
        codes = [c.strip() for c in (h.codes or "").split(",") if c.strip()]
        if not codes:
            return jsonify({"error": "No codes to return"}), 400

        produit = Produit.query.filter_by(name=h.produit).first()
        if not produit:
            return jsonify({"error": "Product not found"}), 404

        duree_entry = DureeAvecStock.query.filter_by(produit_id=produit.id, duree=h.duree).first()
        if not duree_entry:
            return jsonify({"error": "Duration entry not found"}), 404

        # Restore codes → Stock (use per-code price)
        per_code_price = total / len(codes)
        for code in codes:
            db.session.add(Stock(
                fournisseur="(Retour)",
                prix_achat=per_code_price,
                produit_id=produit.id,
                duree=h.duree,
                code=code,
                note=rr.reason,
                canceled_by=reviewer.nom
            ))

        # Update DureeAvecStock quantity
        duree_entry.quantite = (duree_entry.quantite or 0) + len(codes)

        # Refund the buyer
        buyer = User.query.get(h.user_id)
        if not buyer:
            return jsonify({"error": "Buyer not found"}), 404
        buyer.solde = float(buyer.solde) + total

        # Create negative historique for accounting
        db.session.add(Historique(
            user_id=h.user_id,
            produit=h.produit,
            duree=h.duree,
            codes=h.codes,
            montant=-total,
            note=f"Return approved by {reviewer.nom}"
        ))

        # Delete ALL ReturnRequest records for this historique to avoid foreign key issues
        ReturnRequest.query.filter_by(historique_id=h.id).delete()

        # Delete original sale
        db.session.delete(h)

        db.session.commit()

        emit_user_updated(buyer, exclude_user_id=reviewer_id)

        return jsonify({
            "message": "Return approved",
            "request_id": rr.id,
            "refunded_amount": total,
            "buyer_new_solde": float(buyer.solde)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Approval failed: {str(e)}"}), 500
    
@historique_bp.route('/returns/<int:req_id>/reject', methods=['POST'])
@jwt_required()
def reject_return(req_id):
    reviewer_id = get_jwt_identity()
    reviewer = User.query.get(reviewer_id)
    if not reviewer:
        return jsonify({"error": "User not found"}), 404
    if reviewer.role not in ["manager", "admin_boss"]:
        return jsonify({"error": "Only manager/admin_boss can reject returns"}), 403

    rr = ReturnRequest.query.get(req_id)
    if not rr or rr.status != "pending":
        return jsonify({"error": "Pending return request not found"}), 404

    try:
        rr.status = "rejected"
        rr.reviewed_by = reviewer.id
        rr.reviewed_at = func.now()
        db.session.commit()
        return jsonify({"message": "Return rejected", "request_id": rr.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Rejection failed: {str(e)}"}), 500
