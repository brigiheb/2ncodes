from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from .. import db
from ..models.user import User
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye
import logging

# Set up logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

def apply_filters_and_paginate(query, etat, search, page, per_page):
    try:
        # Determine the model based on etat or query type
        model = TransactionPaye if etat == 'paye' else TransactionImpaye

        if search:
            # Join with User for both envoyee_par and recue_par
            query = query.join(User, or_(
                User.id == model.envoyee_par,
                User.id == model.recue_par
            )).filter(or_(
                User.nom.ilike(f"%{search}%"),
                model.montant.ilike(f"%{search}%"),
            ))

        # Apply ordering based on etat
        if etat == 'paye':
            query = query.order_by(TransactionPaye.id.desc())
        elif etat == 'impaye':
            query = query.order_by(TransactionImpaye.id.desc())

        # Paginate the query
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "items": pagination.items,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total
        }
    except Exception as e:
        logger.error(f"Error in apply_filters_and_paginate: {str(e)}")
        raise

@transactions_bp.route('/manager/all', methods=['GET'])
@jwt_required()
def manager_all_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role != 'manager':
            return jsonify({"error": "Access denied"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        paye_query = TransactionPaye.query
        impaye_query = TransactionImpaye.query

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in manager_all_transactions: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/manager/mine', methods=['GET'])
@jwt_required()
def manager_my_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role != 'manager':
            return jsonify({"error": "Access denied"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par == user_id) | (TransactionPaye.recue_par == user_id)
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par == user_id) | (TransactionImpaye.recue_par == user_id)
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in manager_my_transactions: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/admin/mine', methods=['GET'])
@jwt_required()
def admin_my_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role != 'admin':
            return jsonify({"error": "Access denied"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par == user_id) | (TransactionPaye.recue_par == user_id)
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par == user_id) | (TransactionImpaye.recue_par == user_id)
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in admin_my_transactions: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/admin/revendeurs', methods=['GET'])
@jwt_required()
def admin_revendeur_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role != 'admin':
            return jsonify({"error": "Access denied"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        revendeur_ids = [r.id for r in User.query.filter_by(responsable=user_id).all()]

        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par.in_(revendeur_ids)) | (TransactionPaye.recue_par.in_(revendeur_ids))
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par.in_(revendeur_ids)) | (TransactionImpaye.recue_par.in_(revendeur_ids))
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in admin_revendeur_transactions: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/revendeur/mine', methods=['GET'])
@jwt_required()
def revendeur_my_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role != 'revendeur':
            return jsonify({"error": "Access denied"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par == user_id) | (TransactionPaye.recue_par == user_id)
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par == user_id) | (TransactionImpaye.recue_par == user_id)
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in revendeur_my_transactions: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500
    
@transactions_bp.route('/admin/user/<int:target_user_id>', methods=['GET'])
@jwt_required()
def get_transactions_by_user_id(target_user_id):
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role != 'admin':
            return jsonify({"error": "Access denied"}), 403

        # Check if target user exists
        target_user = User.query.get(target_user_id)
        if not target_user:
            return jsonify({"error": "User not found"}), 404

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par == target_user_id) | (TransactionPaye.recue_par == target_user_id)
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par == target_user_id) | (TransactionImpaye.recue_par == target_user_id)
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in get_transactions_by_user_id: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500
    
@transactions_bp.route('/manager/user/<int:target_user_id>', methods=['GET'])
@jwt_required()
def manager_get_transactions_by_user(target_user_id):
    try:
        manager_id = get_jwt_identity()
        manager = User.query.get(manager_id)

        if manager.role != 'manager':
            return jsonify({"error": "Access denied"}), 403

        target_user = User.query.get(target_user_id)
        if not target_user:
            return jsonify({"error": "User not found"}), 404

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # ✅ Only transactions between manager and this user (sender/receiver pairs)
        paye_query = TransactionPaye.query.filter(
            ((TransactionPaye.envoyee_par == manager_id) & (TransactionPaye.recue_par == target_user_id)) |
            ((TransactionPaye.envoyee_par == target_user_id) & (TransactionPaye.recue_par == manager_id))
        )
        impaye_query = TransactionImpaye.query.filter(
            ((TransactionImpaye.envoyee_par == manager_id) & (TransactionImpaye.recue_par == target_user_id)) |
            ((TransactionImpaye.envoyee_par == target_user_id) & (TransactionImpaye.recue_par == manager_id))
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200
    except Exception as e:
        logger.error(f"Error in manager_get_transactions_by_user: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500
    
@transactions_bp.route('/admin/revendeur/<int:revendeur_id>', methods=['GET'])
@jwt_required()
def admin_get_transactions_with_my_revendeur(revendeur_id):
    try:
        admin_id = get_jwt_identity()
        admin = User.query.get(admin_id)

        if not admin or admin.role != 'admin':
            return jsonify({"error": "Access denied"}), 403

        # Recursively get all revendeur IDs managed by this admin
        def get_sub_revendeur_ids(admin_id):
            revendeur_ids = []
            direct_revendeurs = User.query.filter_by(responsable=admin_id, role="revendeur").all()
            revendeur_ids.extend([r.id for r in direct_revendeurs])
            sub_admins = User.query.filter_by(responsable=admin_id, role="admin").all()
            for sub_admin in sub_admins:
                revendeur_ids.extend(get_sub_revendeur_ids(sub_admin.id))
            return revendeur_ids

        allowed_revendeur_ids = get_sub_revendeur_ids(admin_id)

        if revendeur_id not in allowed_revendeur_ids:
            return jsonify({"error": "You do not have access to this revendeur's transactions"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # ✅ Only transactions between this admin and the given revendeur
        paye_query = TransactionPaye.query.filter(
            ((TransactionPaye.envoyee_par == admin_id) & (TransactionPaye.recue_par == revendeur_id)) |
            ((TransactionPaye.envoyee_par == revendeur_id) & (TransactionPaye.recue_par == admin_id))
        )
        impaye_query = TransactionImpaye.query.filter(
            ((TransactionImpaye.envoyee_par == admin_id) & (TransactionImpaye.recue_par == revendeur_id)) |
            ((TransactionImpaye.envoyee_par == revendeur_id) & (TransactionImpaye.recue_par == admin_id))
        )

        paye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}
        impaye_result = {"items": [], "page": page, "per_page": per_page, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, page, per_page)

        return jsonify({
            "paye": {
                "transactions": [t.to_dict() for t in paye_result["items"]],
                "page": paye_result["page"],
                "per_page": paye_result["per_page"],
                "total": paye_result["total"]
            },
            "impaye": {
                "transactions": [t.to_dict() for t in impaye_result["items"]],
                "page": impaye_result["page"],
                "per_page": impaye_result["per_page"],
                "total": impaye_result["total"]
            }
        }), 200

    except Exception as e:
        logger.error(f"Error in admin_get_transactions_with_my_revendeur: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

