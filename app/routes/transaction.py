from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models.user import User
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')


def filter_transactions(query, etat):
    if etat == 'paye':
        return query.all(), 'paye'
    elif etat == 'impaye':
        return query.all(), 'impaye'
    return query.all(), 'all'


@transactions_bp.route('/manager/all', methods=['GET'])
@jwt_required()
def manager_all_transactions():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role != 'manager':
        return jsonify({"error": "Access denied"}), 403

    etat = request.args.get('etat')

    paye_query = TransactionPaye.query
    impaye_query = TransactionImpaye.query

    paye_transactions, _ = filter_transactions(paye_query, etat if etat == 'paye' else '')
    impaye_transactions, _ = filter_transactions(impaye_query, etat if etat == 'impaye' else '')

    return jsonify({
        "paye": [t.to_dict() for t in paye_transactions] if etat in [None, 'paye'] else [],
        "impaye": [t.to_dict() for t in impaye_transactions] if etat in [None, 'impaye'] else []
    }), 200


@transactions_bp.route('/manager/mine', methods=['GET'])
@jwt_required()
def manager_my_transactions():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role != 'manager':
        return jsonify({"error": "Access denied"}), 403

    etat = request.args.get('etat')

    paye_query = TransactionPaye.query.filter(
        (TransactionPaye.envoyee_par == user_id) | (TransactionPaye.recue_par == user_id)
    )
    impaye_query = TransactionImpaye.query.filter(
        (TransactionImpaye.envoyee_par == user_id) | (TransactionImpaye.recue_par == user_id)
    )

    paye_transactions, _ = filter_transactions(paye_query, etat if etat == 'paye' else '')
    impaye_transactions, _ = filter_transactions(impaye_query, etat if etat == 'impaye' else '')

    return jsonify({
        "paye": [t.to_dict() for t in paye_transactions] if etat in [None, 'paye'] else [],
        "impaye": [t.to_dict() for t in impaye_transactions] if etat in [None, 'impaye'] else []
    }), 200


@transactions_bp.route('/admin/mine', methods=['GET'])
@jwt_required()
def admin_my_transactions():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role != 'admin':
        return jsonify({"error": "Access denied"}), 403

    etat = request.args.get('etat')

    paye_query = TransactionPaye.query.filter(
        (TransactionPaye.envoyee_par == user_id) | (TransactionPaye.recue_par == user_id)
    )
    impaye_query = TransactionImpaye.query.filter(
        (TransactionImpaye.envoyee_par == user_id) | (TransactionImpaye.recue_par == user_id)
    )

    paye_transactions, _ = filter_transactions(paye_query, etat if etat == 'paye' else '')
    impaye_transactions, _ = filter_transactions(impaye_query, etat if etat == 'impaye' else '')

    return jsonify({
        "paye": [t.to_dict() for t in paye_transactions] if etat in [None, 'paye'] else [],
        "impaye": [t.to_dict() for t in impaye_transactions] if etat in [None, 'impaye'] else []
    }), 200


@transactions_bp.route('/admin/revendeurs', methods=['GET'])
@jwt_required()
def admin_revendeur_transactions():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role != 'admin':
        return jsonify({"error": "Access denied"}), 403

    etat = request.args.get('etat')

    revendeur_ids = [r.id for r in User.query.filter_by(responsable=user_id).all()]

    paye_query = TransactionPaye.query.filter(
        (TransactionPaye.envoyee_par.in_(revendeur_ids)) | (TransactionPaye.recue_par.in_(revendeur_ids))
    )
    impaye_query = TransactionImpaye.query.filter(
        (TransactionImpaye.envoyee_par.in_(revendeur_ids)) | (TransactionImpaye.recue_par.in_(revendeur_ids))
    )

    paye_transactions, _ = filter_transactions(paye_query, etat if etat == 'paye' else '')
    impaye_transactions, _ = filter_transactions(impaye_query, etat if etat == 'impaye' else '')

    return jsonify({
        "paye": [t.to_dict() for t in paye_transactions] if etat in [None, 'paye'] else [],
        "impaye": [t.to_dict() for t in impaye_transactions] if etat in [None, 'impaye'] else []
    }), 200


@transactions_bp.route('/revendeur/mine', methods=['GET'])
@jwt_required()
def revendeur_my_transactions():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role != 'revendeur':
        return jsonify({"error": "Access denied"}), 403

    etat = request.args.get('etat')

    paye_query = TransactionPaye.query.filter(
        (TransactionPaye.envoyee_par == user_id) | (TransactionPaye.recue_par == user_id)
    )
    impaye_query = TransactionImpaye.query.filter(
        (TransactionImpaye.envoyee_par == user_id) | (TransactionImpaye.recue_par == user_id)
    )

    paye_transactions, _ = filter_transactions(paye_query, etat if etat == 'paye' else '')
    impaye_transactions, _ = filter_transactions(impaye_query, etat if etat == 'impaye' else '')

    return jsonify({
        "paye": [t.to_dict() for t in paye_transactions] if etat in [None, 'paye'] else [],
        "impaye": [t.to_dict() for t in impaye_transactions] if etat in [None, 'impaye'] else []
    }), 200
