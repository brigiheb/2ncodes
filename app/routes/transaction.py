from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, func
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
from .. import db
from ..models.user import User
from ..models.transaction_paye import TransactionPaye
from ..models.transaction_impaye import TransactionImpaye
import logging
import traceback
from datetime import datetime, timedelta
from flask_socketio import SocketIO
from app import socketio, db
from app.utils.socket_state import connected_users

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Helper function to parse duree string to timedelta
def parse_duree(duree_str):
    try:
        if not duree_str:
            return None
        parts = duree_str.split()
        if not parts or len(parts) < 2:
            return None
        value = int(parts[0])
        unit = parts[1].lower()
        if unit.startswith('jour'):
            return timedelta(days=value)
        elif unit.startswith('mois'):
            return timedelta(days=value * 30)  # Approximate
        elif unit.startswith('semaine'):
            return timedelta(weeks=value)
        return None
    except (ValueError, IndexError):
        return None

# Helper function to format overdue duration
def format_overdue_duration(time_until_expiration):
    try:
        if time_until_expiration >= timedelta(0):
            return "moins d’un jour"
        overdue_duration = -time_until_expiration
        total_days = overdue_duration.total_seconds() / (60 * 60 * 24)
        if total_days < 1:
            return "moins d’un jour"
        elif total_days < 7:
            days = round(total_days)
            return f"{days} {'jour' if days == 1 else 'jours'}"
        elif total_days < 30:
            weeks = round(total_days / 7)
            return f"{weeks} {'semaine' if weeks == 1 else 'semaines'}"
        else:
            months = round(total_days / 30)
            return f"{months} {'mois' if months == 1 else 'mois'}"
    except Exception as e:
        logger.error(f"Error in format_overdue_duration: {str(e)}\n{traceback.format_exc()}")
        return "inconnu"

# Helper function to check and emit reminders
def check_and_emit_reminders():
    try:
        now = datetime.utcnow()
        impayes = TransactionImpaye.query.all()
        logger.debug(f"Checking {len(impayes)} unpaid transactions at {now}")
        for impaye in impayes:
            duree = parse_duree(impaye.duree)
            if not duree:
                logger.warning(f"Invalid duree for transaction {impaye.id}: {impaye.duree}")
                continue
            expiration = impaye.date_transaction + duree
            time_until_expiration = expiration - now
            sender = User.query.get(impaye.envoyee_par)
            receiver = User.query.get(impaye.recue_par)
            if not sender or not receiver:
                logger.warning(f"Invalid users for transaction {impaye.id}: sender={impaye.envoyee_par}, receiver={impaye.recue_par}")
                continue
            notification_data = {
                'transaction_id': impaye.id,
                'montant': float(impaye.montant),
                'envoyee_par': sender.nom,
                'recue_par': receiver.nom,
                'duree': impaye.duree,
                'date_transaction': impaye.date_transaction.isoformat(),
                'expiration': expiration.isoformat()
            }
            if timedelta(hours=12) <= time_until_expiration <= timedelta(hours=36):
                for user_id in [impaye.envoyee_par, impaye.recue_par]:
                    sid = connected_users.get(str(user_id))
                    if sid:
                        socketio.emit('transaction_reminder', {
                            'type': 'before_expiration',
                            'message': f"Échéance dans 1 jour : {impaye.montant} TND",
                            **notification_data
                        }, room=sid)
                        logger.debug(f"Emitted 1-day before reminder to user {user_id} for transaction {impaye.id}")
            elif timedelta(hours=-12) <= time_until_expiration <= timedelta(hours=12):
                for user_id in [impaye.envoyee_par, impaye.recue_par]:
                    sid = connected_users.get(str(user_id))
                    if sid:
                        socketio.emit('transaction_reminder', {
                            'type': 'on_expiration',
                            'message': f"Échéance aujourd'hui : {impaye.montant} TND",
                            **notification_data
                        }, room=sid)
                        logger.debug(f"Emitted expiration day reminder to user {user_id} for transaction {impaye.id}")
            elif time_until_expiration < timedelta(hours=-12):
                user_id = impaye.envoyee_par
                sid = connected_users.get(str(user_id))
                if sid:
                    overdue_duration = format_overdue_duration(time_until_expiration)
                    socketio.emit('transaction_reminder', {
                        'type': 'after_expiration',
                        'message': f"En retard de {overdue_duration} : {impaye.montant} TND",
                        **notification_data
                    }, room=sid)
                    logger.debug(f"Emitted overdue reminder to sender {user_id} for transaction {impaye.id}")
    except Exception as e:
        logger.error(f"Error in check_and_emit_reminders: {str(e)}\n{traceback.format_exc()}")

@socketio.on('get_transaction_reminders')
def handle_get_transaction_reminders(data):
    user_id = data.get('user_id')
    if not user_id:
        logger.warning("No user_id provided in get_transaction_reminders")
        return
    user = User.query.get(user_id)
    if not user:
        logger.warning(f"User not found: {user_id}")
        return
    impayes = TransactionImpaye.query.filter(
        (TransactionImpaye.envoyee_par == user_id) | 
        (TransactionImpaye.recue_par == user_id)
    ).all()
    now = datetime.utcnow()
    for impaye in impayes:
        duree = parse_duree(impaye.duree)
        if not duree:
            logger.warning(f"Invalid duree for transaction {impaye.id}: {impaye.duree}")
            continue
        expiration = impaye.date_transaction + duree
        time_until_expiration = expiration - now
        sender = User.query.get(impaye.envoyee_par)
        receiver = User.query.get(impaye.recue_par)
        if not sender or not receiver:
            logger.warning(f"Invalid users for transaction {impaye.id}: sender={impaye.envoyee_par}, receiver={impaye.recue_par}")
            continue
        notification_data = {
            'transaction_id': impaye.id,
            'montant': float(impaye.montant),
            'envoyee_par': sender.nom,
            'recue_par': receiver.nom,
            'duree': impaye.duree,
            'date_transaction': impaye.date_transaction.isoformat(),
            'expiration': expiration.isoformat()
        }
        sid = connected_users.get(str(user_id))
        if not sid:
            logger.debug(f"No socket connection for user {user_id} for transaction {impaye.id}")
            continue
        if timedelta(hours=12) <= time_until_expiration <= timedelta(hours=36):
            socketio.emit('transaction_reminder', {
                'type': 'before_expiration',
                'message': f"Échéance dans 1 jour : {impaye.montant} TND",
                **notification_data
            }, room=sid)
        elif timedelta(hours=-12) <= time_until_expiration <= timedelta(hours=12):
            socketio.emit('transaction_reminder', {
                'type': 'on_expiration',
                'message': f"Échéance aujourd'hui : {impaye.montant} TND",
                **notification_data
            }, room=sid)
        elif time_until_expiration < timedelta(hours=-12) and user_id == impaye.envoyee_par:
            overdue_duration = format_overdue_duration(time_until_expiration)
            socketio.emit('transaction_reminder', {
                'type': 'after_expiration',
                'message': f"En retard de {overdue_duration} : {impaye.montant} TND",
                **notification_data
            }, room=sid)

@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('userId')
    if user_id:
        connected_users[user_id] = request.sid
        logger.debug(f"User {user_id} connected with SID: {request.sid}")
        socketio.start_background_task(lambda: socketio.sleep(30) or check_and_emit_reminders())

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

def apply_filters_and_paginate(query, etat, search, envoyee_par, recue_par, start_date, end_date, page, per_page):
    try:
        model = TransactionPaye if etat == 'paye' else TransactionImpaye
        logger.debug(f"Applying filters: etat={etat}, search={search}, envoyee_par={envoyee_par}, recue_par={recue_par}, start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}")

        # Apply envoyee_par and recue_par filters if they are valid integers
        if isinstance(envoyee_par, int):
            query = query.filter(model.envoyee_par == envoyee_par)
            logger.debug(f"Applied envoyee_par filter: {query}")
        if isinstance(recue_par, int):
            query = query.filter(model.recue_par == recue_par)
            logger.debug(f"Applied recue_par filter: {query}")

        # Apply date filters if provided
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(model.date_transaction >= start_date)
                logger.debug(f"Applied start_date filter: {query}")
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}")
                raise ValueError("Invalid start_date format. Use YYYY-MM-DD.")
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                # Include full end date by adding 1 day
                query = query.filter(model.date_transaction < end_date + timedelta(days=1))
                logger.debug(f"Applied end_date filter: {query}")
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}")
                raise ValueError("Invalid end_date format. Use YYYY-MM-DD.")

        # Apply search filter
        if search:
            try:
                search_float = float(search) if search.replace('.', '', 1).isdigit() else None
                user_filter = User.nom.ilike(f"%{search}%")
                montant_filter = model.montant == search_float if search_float is not None else func.cast(model.montant, db.String).ilike(f"%{search}%")
                query = query.join(User, or_(
                    User.id == model.envoyee_par,
                    User.id == model.recue_par
                ), isouter=True).filter(or_(user_filter, montant_filter))
                logger.debug(f"Applied search filter: {query}")
            except ValueError:
                query = query.join(User, or_(
                    User.id == model.envoyee_par,
                    User.id == model.recue_par
                ), isouter=True).filter(User.nom.ilike(f"%{search}%"))
                logger.debug(f"Applied non-numeric search filter: {query}")

        # Sort by date_transaction DESC, and for paye, also by date_paiement DESC
        if etat == 'paye':
            query = query.order_by(TransactionPaye.date_transaction.desc(), TransactionPaye.date_paiement.desc())
        elif etat == 'impaye':
            query = query.order_by(TransactionImpaye.date_transaction.desc())

        # Handle pagination or fetch all if page/per_page not provided
        if page is None or per_page is None:
            items = query.all()
            return {
                "items": items,
                "page": 1,
                "per_page": len(items),
                "total": len(items)
            }
        else:
            if page < 1 or per_page < 1:
                raise ValueError("Page and per_page must be positive integers")
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            logger.debug(f"Pagination result: page={pagination.page}, total={pagination.total}")
            return {
                "items": pagination.items,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total
            }
    except ValueError as ve:
        logger.error(f"Invalid input in apply_filters_and_paginate: {str(ve)}\n{traceback.format_exc()}")
        raise
    except OperationalError as oe:
        logger.error(f"Database operational error in apply_filters_and_paginate: {str(oe)}\n{traceback.format_exc()}")
        raise SQLAlchemyError(f"Database operation failed: {str(oe)}")
    except ProgrammingError as pe:
        logger.error(f"Database programming error in apply_filters_and_paginate: {str(pe)}\n{traceback.format_exc()}")
        raise SQLAlchemyError(f"Invalid database query: {str(pe)}")
    except SQLAlchemyError as se:
        logger.error(f"Database error in apply_filters_and_paginate: {str(se)}\n{traceback.format_exc()}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in apply_filters_and_paginate: {str(e)}\n{traceback.format_exc()}")
        raise

def calculate_transaction_metrics(paye_query, impaye_query):
    try:
        paye_subq = paye_query.statement.subquery()
        impaye_subq = impaye_query.statement.subquery()
        total_paye = db.session.query(func.coalesce(func.sum(paye_subq.c.montant), 0)).scalar()
        total_impaye = db.session.query(func.coalesce(func.sum(impaye_subq.c.montant), 0)).scalar()
        paye_count = db.session.query(func.count()).select_from(paye_subq).scalar()
        impaye_count = db.session.query(func.count()).select_from(impaye_subq).scalar()
        difference = float(total_paye) - float(total_impaye)
        total_transactions = paye_count + impaye_count
        daily_paye = db.session.query(
            func.date_format(paye_subq.c.date_transaction, '%d/%m/%Y').label('day'),
            func.coalesce(func.sum(paye_subq.c.montant), 0).label('montant')
        ).group_by('day').order_by('day').all()
        daily_impaye = db.session.query(
            func.date_format(impaye_subq.c.date_transaction, '%d/%m/%Y').label('day'),
            func.coalesce(func.sum(impaye_subq.c.montant), 0).label('montant')
        ).group_by('day').order_by('day').all()
        daily_totals = {}
        for day, montant in daily_paye:
            daily_totals[day] = daily_totals.get(day, 0) + float(montant)
        for day, montant in daily_impaye:
            daily_totals[day] = daily_totals.get(day, 0) + float(montant)
        daily_data = [{"name": day, "montant": montant} for day, montant in sorted(daily_totals.items())]
        monthly_paye = db.session.query(
            func.date_format(paye_subq.c.date_transaction, '%Y-%m').label('month'),
            func.coalesce(func.sum(paye_subq.c.montant), 0).label('montant')
        ).group_by('month').order_by('month').all()
        monthly_impaye = db.session.query(
            func.date_format(impaye_subq.c.date_transaction, '%Y-%m').label('month'),
            func.coalesce(func.sum(impaye_subq.c.montant), 0).label('montant')
        ).group_by('month').order_by('month').all()
        monthly_totals = {}
        for month, montant in monthly_paye:
            monthly_totals[month] = monthly_totals.get(month, 0) + float(montant)
        for month, montant in monthly_impaye:
            monthly_totals[month] = monthly_totals.get(month, 0) + float(montant)
        monthly_data = [{"name": month, "montant": montant} for month, montant in sorted(monthly_totals.items())]
        return {
            "total_paye": float(total_paye),
            "total_impaye": float(total_impaye),
            "difference": float(difference),
            "total_transactions": total_transactions,
            "daily": daily_data,
            "monthly": monthly_data
        }
    except Exception as e:
        logger.error(f"Error in calculate_transaction_metrics: {str(e)}\n{traceback.format_exc()}")
        raise

@transactions_bp.route('/manager/all', methods=['GET'])
@jwt_required()
def manager_all_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if user.role not in ["manager","admin_boss"]:
            return jsonify({"error": "Access denied"}), 403
        etat = request.args.get('etat')
        search = request.args.get('search', '')
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        paye_query = TransactionPaye.query
        impaye_query = TransactionImpaye.query
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in manager_all_transactions: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in manager_all_transactions: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Error in manager_all_transactions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/manager/mine', methods=['GET'])
@jwt_required()
def manager_my_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user or user.role not in ["manager", "admin_boss"]:
            logger.warning(f"Access denied for user_id={user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access denied"}), 403

        etat = request.args.get('etat')
        search = request.args.get('search', '')
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)

        logger.debug(
            f"Request params: etat={etat}, search={search}, recue_par={recue_par}, "
            f"start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}"
        )

        paye_query = TransactionPaye.query.filter(TransactionPaye.envoyee_par == user_id)
        impaye_query = TransactionImpaye.query.filter(TransactionImpaye.envoyee_par == user_id)

        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}

        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(
                paye_query, 'paye', search, None, recue_par, start_date, end_date, page, per_page
            )
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(
                impaye_query, 'impaye', search, None, recue_par, start_date, end_date, page, per_page
            )

        metrics = calculate_transaction_metrics(paye_query, impaye_query)

        logger.debug("Returning response for manager_my_transactions")
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
            },
            "metrics": metrics
        }), 200

    except ValueError as ve:
        logger.error(f"Invalid input in manager_my_transactions: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in manager_my_transactions: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in manager_my_transactions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@transactions_bp.route('/admin/mine', methods=['GET'])
@jwt_required()
def admin_my_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role != 'admin':
            logger.warning(f"Access denied for user_id={user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access denied"}), 403
        etat = request.args.get('etat')
        search = request.args.get('search', '')
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        logger.debug(f"Request params: etat={etat}, search={search}, envoyee_par={envoyee_par}, recue_par={recue_par}, start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}")
        paye_query = TransactionPaye.query.filter(TransactionPaye.envoyee_par == user_id)
        impaye_query = TransactionImpaye.query.filter(TransactionImpaye.envoyee_par == user_id)
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
        logger.debug("Returning response for admin_my_transactions")
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in admin_my_transactions: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in admin_my_transactions: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in admin_my_transactions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@transactions_bp.route('/admin/revendeurs', methods=['GET'])
@jwt_required()
def admin_revendeur_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if user.role != 'admin':
            return jsonify({"error": "Access denied"}), 403
        def get_sub_revendeur_ids(admin_id):
            revendeur_ids = []
            direct_revendeurs = User.query.filter_by(responsable=admin_id, role="revendeur").all()
            revendeur_ids.extend([r.id for r in direct_revendeurs])
            sub_admins = User.query.filter_by(responsable=admin_id, role="admin").all()
            for sub_admin in sub_admins:
                revendeur_ids.extend(get_sub_revendeur_ids(sub_admin.id))
            return revendeur_ids
        revendeur_ids = get_sub_revendeur_ids(user_id)
        etat = request.args.get('etat')
        search = request.args.get('search', '')
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        paye_query = TransactionPaye.query.filter(TransactionPaye.recue_par.in_(revendeur_ids))
        impaye_query = TransactionImpaye.query.filter(TransactionImpaye.recue_par.in_(revendeur_ids))
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in admin_revendeur_transactions: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in admin_revendeur_transactions: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Error in admin_revendeur_transactions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/revendeur/mine', methods=['GET'])
@jwt_required()
def revendeur_my_transactions():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role != 'revendeur':
            logger.warning(f"Access denied for user_id={user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access denied"}), 403
        etat = request.args.get('etat')
        search = request.args.get('search', '')
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        logger.debug(f"Request params: etat={etat}, search={search}, envoyee_par={envoyee_par}, recue_par={recue_par}, start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}")
        paye_query = TransactionPaye.query.filter(TransactionPaye.recue_par == user_id)
        impaye_query = TransactionImpaye.query.filter(TransactionImpaye.recue_par == user_id)
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
        logger.debug("Returning response for revendeur_my_transactions")
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in revendeur_my_transactions: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in revendeur_my_transactions: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in revendeur_my_transactions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@transactions_bp.route('/admin/user/<int:target_user_id>', methods=['GET'])
@jwt_required()
def get_transactions_by_user_id(target_user_id):
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role != 'admin':
            logger.warning(f"Access denied for user_id={user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access denied"}), 403
        target_user = User.query.get(target_user_id)
        if not target_user:
            logger.warning(f"Target user not found: target_user_id={target_user_id}")
            return jsonify({"error": "User not found"}), 404
        etat = request.args.get('etat')
        search = request.args.get('search', '')
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        logger.debug(f"Request params: etat={etat}, search={search}, envoyee_par={envoyee_par}, recue_par={recue_par}, start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}")
        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par == target_user_id) | (TransactionPaye.recue_par == target_user_id)
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par == target_user_id) | (TransactionImpaye.recue_par == target_user_id)
        )
        if not any([etat, search, envoyee_par, recue_par, start_date, end_date, page, per_page]):
            paye_transactions = paye_query.all()
            impaye_transactions = impaye_query.all()
            metrics = calculate_transaction_metrics(paye_query, impaye_query)
            return jsonify({
                "paye": {
                    "transactions": [t.to_dict() for t in paye_transactions],
                    "page": 1,
                    "per_page": len(paye_transactions),
                    "total": len(paye_transactions)
                },
                "impaye": {
                    "transactions": [t.to_dict() for t in impaye_transactions],
                    "page": 1,
                    "per_page": len(impaye_transactions),
                    "total": len(impaye_transactions)
                },
                "metrics": metrics
            }), 200
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
        logger.debug("Returning response for get_transactions_by_user_id")
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in get_transactions_by_user_id: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in get_transactions_by_user_id: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_transactions_by_user_id: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@transactions_bp.route('/manager/user/<int:target_user_id>', methods=['GET'])
@jwt_required()
def manager_get_transactions_by_user(target_user_id):
    try:
        manager_id = get_jwt_identity()
        manager = User.query.get(manager_id)
        if not manager or manager.role not in ["manager","admin_boss"]:
            logger.warning(f"Access denied for manager_id={manager_id}, role={manager.role if manager else 'None'}")
            return jsonify({"error": "Access denied"}), 403
        target_user = User.query.get(target_user_id)
        if not target_user:
            logger.warning(f"Target user not found: target_user_id={target_user_id}")
            return jsonify({"error": "User not found"}), 404
        etat = request.args.get('etat')
        search = request.args.get('search', '')
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        logger.debug(f"Request params: etat={etat}, search={search}, envoyee_par={envoyee_par}, recue_par={recue_par}, start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}")
        paye_query = TransactionPaye.query.filter(
            (TransactionPaye.envoyee_par == target_user_id) | (TransactionPaye.recue_par == target_user_id)
        )
        impaye_query = TransactionImpaye.query.filter(
            (TransactionImpaye.envoyee_par == target_user_id) | (TransactionImpaye.recue_par == target_user_id)
        )
        if not any([etat, search, envoyee_par, recue_par, start_date, end_date, page, per_page]):
            paye_transactions = paye_query.all()
            impaye_transactions = impaye_query.all()
            metrics = calculate_transaction_metrics(paye_query, impaye_query)
            return jsonify({
                "paye": {
                    "transactions": [t.to_dict() for t in paye_transactions],
                    "page": 1,
                    "per_page": len(paye_transactions),
                    "total": len(paye_transactions)
                },
                "impaye": {
                    "transactions": [t.to_dict() for t in impaye_transactions],
                    "page": 1,
                    "per_page": len(impaye_transactions),
                    "total": len(impaye_transactions)
                },
                "metrics": metrics
            }), 200
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
        logger.debug("Returning response for manager_get_transactions_by_user")
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in manager_get_transactions_by_user: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in manager_get_transactions_by_user: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in manager_get_transactions_by_user: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@transactions_bp.route('/admin/revendeur/<int:revendeur_id>', methods=['GET'])
@jwt_required()
def admin_get_transactions_with_my_revendeur(revendeur_id):
    try:
        admin_id = get_jwt_identity()
        admin = User.query.get(admin_id)
        if not admin or admin.role != 'admin':
            return jsonify({"error": "Access denied"}), 403
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
        envoyee_par = request.args.get('envoyee_par', type=int)
        recue_par = request.args.get('recue_par', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)
        logger.debug(f"Request params: etat={etat}, search={search}, envoyee_par={envoyee_par}, recue_par={recue_par}, start_date={start_date}, end_date={end_date}, page={page}, per_page={per_page}")
        paye_query = TransactionPaye.query.filter(
            ((TransactionPaye.envoyee_par == admin_id) & (TransactionPaye.recue_par == revendeur_id)) |
            ((TransactionPaye.envoyee_par == revendeur_id) & (TransactionPaye.recue_par == admin_id))
        )
        impaye_query = TransactionImpaye.query.filter(
            ((TransactionImpaye.envoyee_par == admin_id) & (TransactionImpaye.recue_par == revendeur_id)) |
            ((TransactionImpaye.envoyee_par == revendeur_id) & (TransactionImpaye.recue_par == admin_id))
        )
        paye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        impaye_result = {"items": [], "page": 1, "per_page": 0, "total": 0}
        if etat in [None, '', 'paye', 'all']:
            paye_result = apply_filters_and_paginate(paye_query, 'paye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        if etat in [None, '', 'impaye', 'all']:
            impaye_result = apply_filters_and_paginate(impaye_query, 'impaye', search, envoyee_par, recue_par, start_date, end_date, page, per_page)
        metrics = calculate_transaction_metrics(paye_query, impaye_query)
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
            },
            "metrics": metrics
        }), 200
    except ValueError as ve:
        logger.error(f"Invalid input in admin_get_transactions_with_my_revendeur: {str(ve)}\n{traceback.format_exc()}")
        return jsonify({"error": str(ve)}), 400
    except SQLAlchemyError as se:
        logger.error(f"Database error in admin_get_transactions_with_my_revendeur: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Error in admin_get_transactions_with_my_revendeur: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": "An unexpected error occurred while fetching transactions"}), 500

@transactions_bp.route('/get_filter_options', methods=['GET'])
@jwt_required()
def get_filter_options():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role not in ['manager', 'admin', 'admin_boss', 'revendeur']:
            logger.warning(f"Access denied for user_id={user_id}, role={user.role if user else 'None'}")
            return jsonify({"error": "Access denied"}), 403

        # For all roles, fetch all users involved in transactions (as sender or receiver)
        envoyee_par_paye = db.session.query(
            User.id.label('user_id'),
            User.nom.label('user_name')
        ).join(TransactionPaye, User.id == TransactionPaye.envoyee_par).distinct()
        
        recue_par_paye = db.session.query(
            User.id.label('user_id'),
            User.nom.label('user_name')
        ).join(TransactionPaye, User.id == TransactionPaye.recue_par).distinct()
        
        envoyee_par_impaye = db.session.query(
            User.id.label('user_id'),
            User.nom.label('user_name')
        ).join(TransactionImpaye, User.id == TransactionImpaye.envoyee_par).distinct()
        
        recue_par_impaye = db.session.query(
            User.id.label('user_id'),
            User.nom.label('user_name')
        ).join(TransactionImpaye, User.id == TransactionImpaye.recue_par).distinct()
        
        # Combine all unique users from paid and unpaid transactions
        combined_users = (
            envoyee_par_paye.union(recue_par_paye)
            .union(envoyee_par_impaye)
            .union(recue_par_impaye)
            .order_by(User.nom.asc())
            .all()
        )
        
        # Fetch the earliest and latest transaction dates
        earliest_paye = db.session.query(func.min(TransactionPaye.date_transaction)).scalar()
        latest_paye = db.session.query(func.max(TransactionPaye.date_transaction)).scalar()
        earliest_impaye = db.session.query(func.min(TransactionImpaye.date_transaction)).scalar()
        latest_impaye = db.session.query(func.max(TransactionImpaye.date_transaction)).scalar()
        
        # Determine the overall date range
        earliest_date = min([d for d in [earliest_paye, earliest_impaye] if d is not None], default=None)
        latest_date = max([d for d in [latest_paye, latest_impaye] if d is not None], default=None)
        
        response = {
            "users": [{"id": user.user_id, "name": user.user_name} for user in combined_users],
            "etat_options": ["paye", "impaye", "all"],
            "date_range": {
                "start_date": earliest_date.strftime('%Y-%m-%d') if earliest_date else None,
                "end_date": latest_date.strftime('%Y-%m-%d') if latest_date else None
            }
        }
        logger.debug("Returning filter options")
        return jsonify(response), 200
    except SQLAlchemyError as se:
        logger.error(f"Database error in get_filter_options: {str(se)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error occurred: {str(se)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_filter_options: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    
@transactions_bp.route('/add_tranche', methods=['POST'])
@jwt_required()
def add_tranche():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role not in ['manager','admin_boss', 'admin']:
            return jsonify({"error": "Access denied"}), 403
        data = request.get_json()
        cible_id = data.get('recue_par_id')
        montant = data.get('montant')
        if not cible_id or not montant:
            return jsonify({"error": "recue_par_id and montant are required"}), 400
        if montant <= 0:
            return jsonify({"error": "montant must be positive"}), 400
        impayes = TransactionImpaye.query.filter_by(recue_par=cible_id).order_by(TransactionImpaye.date_transaction.asc()).all()
        if not impayes:
            return jsonify({"error": "No impayé transactions found for this user"}), 404
        remaining = montant
        total_paid = 0
        for impaye in impayes:
            if remaining <= 0:
                break
            deduction = min(remaining, impaye.montant)
            impaye.montant -= deduction
            remaining -= deduction
            total_paid += deduction
        if total_paid == 0:
            return jsonify({"error": "Nothing was deducted from impayé transactions"}), 400
        paye = TransactionPaye(
            envoyee_par=user_id,
            recue_par=cible_id,
            montant=total_paid,
            preuve=None,
            date_transaction=datetime.utcnow(),
            date_paiement=datetime.utcnow()
        )
        db.session.add(paye)
        for impaye in impayes:
            if impaye.montant == 0:
                db.session.delete(impaye)
        db.session.commit()
        paye_total = db.session.query(func.coalesce(func.sum(TransactionPaye.montant), 0)) \
            .filter(TransactionPaye.recue_par == cible_id).scalar()
        impaye_total = db.session.query(func.coalesce(func.sum(TransactionImpaye.montant), 0)) \
            .filter(TransactionImpaye.recue_par == cible_id).scalar()
        return jsonify({
            "message": "Tranche applied and reflected in both paye and impaye.",
            "tranche_montant": total_paid,
            "updated_totals": {
                "paye": float(paye_total),
                "impaye": float(impaye_total or 0)
            },
            "remaining_amount_unapplied": remaining
        }), 200
    except Exception as e:
        logger.error(f"Error in add_tranche: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500