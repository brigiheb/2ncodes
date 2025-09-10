# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.duree_avec_stock import DureeAvecStock
from ..models.product import Produit
from ..models.historique import Historique
from ..models.user import User
from ..models.stock import Stock
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

statistics_bp = Blueprint('statistics', __name__)

def get_subordinate_ids(user_id, user_dict=None):
    """Recursively get all subordinate user IDs under a given user using the 'responsable' field."""
    if user_dict is None:
        user_dict = {user.id: user for user in User.query.all()}
    
    subordinates = []
    for user in user_dict.values():
        if user.responsable == user_id:
            subordinates.append(user.id)
            subordinates.extend(get_subordinate_ids(user.id, user_dict))
    return subordinates

@statistics_bp.route('/duree/<int:duree_id>', methods=['GET'])
def get_duree_statistics(duree_id):
    try:
        duree = DureeAvecStock.query.get(duree_id)
        if not duree:
            return jsonify({"error": f"Duree with id {duree_id} not found"}), 404

        period = request.args.get('period', default='month', type=str).lower()
        start_date = request.args.get('start_date', default=None, type=str)
        end_date = request.args.get('end_date', default=None, type=str)

        valid_periods = ['month', 'year']
        if period not in valid_periods:
            return jsonify({"error": f"Invalid period. Must be one of {valid_periods}"}), 400

        try:
            start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
            end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.utcnow()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD (e.g., 2025-07-15)"}), 400

        product = Produit.query.get(duree.produit_id)
        if not product:
            return jsonify({"error": f"Product with id {duree.produit_id} not found"}), 404

        current_quantity = float(duree.quantite or 0)
        stock = Stock.query.filter_by(
            produit_id=duree.produit_id,
            duree=duree.duree.strip().lower()
        ).first()
        prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0

        history_query = Historique.query.join(
            Produit, Historique.produit == Produit.name
        ).filter(
            Produit.id == duree.produit_id
        ).with_entities(Historique, Produit.type)

        if start:
            history_query = history_query.filter(Historique.date >= func.cast(start, db.Date))
        if end:
            history_query = history_query.filter(Historique.date <= func.cast(end, db.Date))

        history_records = history_query.all()
        logging.info(f"Number of Historique records for {product.name}: {len(history_records)}")

        total_quantity_sold = 0
        total_montant = 0
        for record, product_type in history_records:
            if record.montant is not None:
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                total_quantity_sold += quantity
                total_montant += float(record.montant or 0)
        logging.info(f"Total quantity sold: {total_quantity_sold}")
        logging.info(f"Total montant from Historique: {total_montant}")

        total_revenue = total_montant if total_montant else 0
        total_cost = total_quantity_sold * prix_achat if prix_achat and total_quantity_sold else 0
        profit = float(total_revenue - total_cost) if total_cost else 0.0
        logging.info(f"Total revenue: {total_revenue}, Total cost: {total_cost}, Profit: {profit}")

        monthly_last_month = []
        if not start_date and not end_date:
            end = datetime.utcnow()
            start_last_month = end - timedelta(days=30)
            monthly_stats = (
                Historique.query.join(
                    Produit, Historique.produit == Produit.name
                )
                .filter(Produit.id == duree.produit_id)
                .filter(Historique.date >= func.cast(start_last_month, db.Date))
                .filter(Historique.date <= func.cast(end, db.Date))
                .with_entities(Historique, Produit.type)
                .all()
            )
            daily_data = {}
            for record, product_type in monthly_stats:
                day = record.date.day
                if record.montant is not None:
                    quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                    if day not in daily_data:
                        daily_data[day] = {'quantity': 0, 'revenue': 0}
                    daily_data[day]['quantity'] += quantity
                    daily_data[day]['revenue'] += float(record.montant or 0)
            for day, data in daily_data.items():
                monthly_last_month.append({
                    'period': datetime(end.year, end.month, day).strftime('%Y-%m-%d'),
                    'revenue': float(data['revenue']),
                    'quantity': float(data['quantity']),
                    'profit': float(data['revenue'] - (data['quantity'] * prix_achat)) if data['revenue'] else 0.0
                })
            monthly_last_month.sort(key=lambda x: x['period'])

        custom_period = []
        if start_date and end_date:
            custom_period_stats = (
                Historique.query.join(
                    Produit, Historique.produit == Produit.name
                )
                .filter(Produit.id == duree.produit_id)
                .filter(Historique.date >= func.cast(start, db.Date))
                .filter(Historique.date <= func.cast(end, db.Date))
                .with_entities(Historique, Produit.type)
                .all()
            )
            daily_data = {}
            for record, product_type in custom_period_stats:
                if record.montant is not None:
                    date_key = record.date.strftime('%Y-%m-%d')
                    quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                    revenue = float(record.montant or 0)
                    if date_key not in daily_data:
                        daily_data[date_key] = {'quantity': 0, 'revenue': 0}
                    daily_data[date_key]['quantity'] += quantity
                    daily_data[date_key]['revenue'] += revenue
            for date_key, data in daily_data.items():
                custom_period.append({
                    'period': date_key,
                    'revenue': float(data['revenue']),
                    'quantity': float(data['quantity']),
                    'profit': float(data['revenue'] - (data['quantity'] * prix_achat)) if data['revenue'] else 0.0
                })
            custom_period.sort(key=lambda x: x['period'])

        end_year = datetime.utcnow()
        start_year = end_year - timedelta(days=365)
        yearly_sales = (
            Historique.query.join(
                Produit, Historique.produit == Produit.name
            )
            .filter(Produit.id == duree.produit_id)
            .filter(Historique.date >= func.cast(start_year, db.Date))
            .filter(Historique.date <= func.cast(end_year, db.Date))
            .with_entities(Historique, Produit.type)
            .all()
        )
        monthly_data = {}
        for record, product_type in yearly_sales:
            month = record.date.strftime('%Y-%m')
            if record.montant is not None:
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                if month not in monthly_data:
                    monthly_data[month] = {'quantity': 0, 'revenue': 0}
                monthly_data[month]['quantity'] += quantity
                monthly_data[month]['revenue'] += float(record.montant or 0)
        yearly_sales_data = [
            {
                'period': month,
                'revenue': float(data['revenue']),
                'quantity': float(data['quantity']),
                'profit': float(data['revenue'] - (data['quantity'] * prix_achat)) if data['revenue'] else 0.0
            }
            for month, data in sorted(monthly_data.items())
        ]

        user_dict = {user.id: user for user in User.query.all()}
        annual_users = {}
        for record, product_type in yearly_sales:
            if record.user_id and record.montant is not None:
                user_id = record.user_id
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                revenue = float(record.montant or 0)
                profit = float(revenue - (quantity * prix_achat)) if revenue else 0.0

                if user_id not in annual_users:
                    annual_users[user_id] = {'direct_quantity': 0, 'direct_revenue': 0, 'hierarchical_quantity': 0, 'hierarchical_revenue': 0, 'hierarchical_profit': 0}
                annual_users[user_id]['direct_quantity'] += quantity
                annual_users[user_id]['direct_revenue'] += revenue

                subordinates = get_subordinate_ids(user_id, user_dict)
                all_user_ids = [user_id] + subordinates
                for sub_user_id in all_user_ids:
                    if sub_user_id not in annual_users:
                        annual_users[sub_user_id] = {'direct_quantity': 0, 'direct_revenue': 0, 'hierarchical_quantity': 0, 'hierarchical_revenue': 0, 'hierarchical_profit': 0}
                    annual_users[sub_user_id]['hierarchical_quantity'] += quantity
                    annual_users[sub_user_id]['hierarchical_revenue'] += revenue
                    annual_users[sub_user_id]['hierarchical_profit'] += profit

        annual_user_stats = [
            {
                'user_name': user_dict[user_id].nom if user_id in user_dict else 'Unknown',
                'direct_quantity': data['direct_quantity'],
                'direct_revenue': float(data['direct_revenue']),
                'hierarchical_quantity': data['hierarchical_quantity'],
                'hierarchical_revenue': float(data['hierarchical_revenue']),
                'hierarchical_profit': float(data['hierarchical_profit'])
            }
            for user_id, data in annual_users.items()
        ]

        user_yearly_stats = {}
        for record, product_type in yearly_sales:
            if record.user_id and record.montant is not None:
                user_id = record.user_id
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                revenue = float(record.montant or 0)
                profit = float(revenue - (quantity * prix_achat)) if revenue else 0.0
                if user_id not in user_yearly_stats:
                    user_yearly_stats[user_id] = {'quantity': 0, 'revenue': 0, 'profit': 0}
                user_yearly_stats[user_id]['quantity'] += quantity
                user_yearly_stats[user_id]['revenue'] += revenue
                user_yearly_stats[user_id]['profit'] += profit

        user_yearly_stats_data = [
            {
                'user_name': user_dict[user_id].nom if user_id in user_dict else 'Unknown',
                'year': str(end_year.year),
                'quantity': float(data['quantity']),
                'revenue': float(data['revenue']),
                'profit': float(data['profit'])
            }
            for user_id, data in user_yearly_stats.items()
        ]

        top_users_last_month = []
        end = datetime.utcnow()
        start_last_month = end - timedelta(days=30)
        top_users_query = (
            db.session.query(Historique.user_id, User.nom, func.count(Historique.id).label('sales_count'))
            .join(User, Historique.user_id == User.id)
            .join(Produit, Historique.produit == Produit.name)
            .filter(Produit.id == duree.produit_id)
            .filter(Historique.date >= func.cast(start_last_month, db.Date))
            .filter(Historique.date <= func.cast(end, db.Date))
            .group_by(Historique.user_id, User.nom)
            .order_by(func.count(Historique.id).desc())
            .limit(5)
            .all()
        )
        for user in top_users_query:
            if user.user_id:
                user_records = (
                    Historique.query.join(
                        Produit, Historique.produit == Produit.name
                    )
                    .filter(Historique.user_id == user.user_id)
                    .filter(Produit.id == duree.produit_id)
                    .filter(Historique.date >= func.cast(start_last_month, db.Date))
                    .filter(Historique.date <= func.cast(end, db.Date))
                    .with_entities(Historique, Produit.type)
                    .all()
                )
                total_quantity = 0
                total_revenue = 0
                for record, product_type in user_records:
                    if record.montant is not None:
                        quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                        total_quantity += quantity
                        total_revenue += float(record.montant or 0)
                profit = float(total_revenue - (total_quantity * prix_achat)) if total_cost else 0.0
                top_users_last_month.append({
                    'user_name': user.nom,
                    'sales_count': user.sales_count,
                    'total_revenue': float(total_revenue),
                    'quantity': float(total_quantity),
                    'profit': float(profit)
                })

        top_users_custom = []
        if start_date and end_date:
            top_users_query = (
                db.session.query(Historique.user_id, User.nom, func.count(Historique.id).label('sales_count'))
                .join(User, Historique.user_id == User.id)
                .join(Produit, Historique.produit == Produit.name)
                .filter(Produit.id == duree.produit_id)
                .filter(Historique.date >= func.cast(start, db.Date))
                .filter(Historique.date <= func.cast(end, db.Date))
                .group_by(Historique.user_id, User.nom)
                .order_by(func.count(Historique.id).desc())
                .limit(5)
                .all()
            )
            for user in top_users_query:
                if user.user_id:
                    user_records = (
                        Historique.query.join(
                            Produit, Historique.produit == Produit.name
                        )
                        .filter(Historique.user_id == user.user_id)
                        .filter(Produit.id == duree.produit_id)
                        .filter(Historique.date >= func.cast(start, db.Date))
                        .filter(Historique.date <= func.cast(end, db.Date))
                        .with_entities(Historique, Produit.type)
                        .all()
                    )
                    total_quantity = 0
                    total_revenue = 0
                    for record, product_type in user_records:
                        if record.montant is not None:
                            quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                            total_quantity += quantity
                            total_revenue += float(record.montant or 0)
                    profit = float(total_revenue - (total_quantity * prix_achat)) if total_cost else 0.0
                    top_users_custom.append({
                        'user_name': user.nom,
                        'sales_count': user.sales_count,
                        'total_revenue': float(total_revenue),
                        'quantity': float(total_quantity),
                        'profit': float(profit)
                    })

        prev_month_start = func.cast(end - timedelta(days=60), db.Date) if not start_date else func.cast(start - timedelta(days=(end - start).days), db.Date)
        prev_month_end = func.cast(end - timedelta(days=30), db.Date) if not start_date else func.cast(start, db.Date)
        prev_month_records = (
            Historique.query.join(
                Produit, Historique.produit == Produit.name
            )
            .filter(Produit.id == duree.produit_id)
            .filter(Historique.date >= prev_month_start)
            .filter(Historique.date < prev_month_end)
            .with_entities(Historique, Produit.type)
            .all()
        )
        prev_month_quantity = 0
        prev_month_revenue = 0
        for record, product_type in prev_month_records:
            if record.montant is not None:
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                prev_month_quantity += quantity
                prev_month_revenue += float(record.montant or 0)

        current_month_records = (
            Historique.query.join(
                Produit, Historique.produit == Produit.name
            )
            .filter(Produit.id == duree.produit_id)
            .filter(Historique.date >= func.cast(end - timedelta(days=30), db.Date) if not start_date else func.cast(start, db.Date))
            .filter(Historique.date <= func.cast(end, db.Date))
            .with_entities(Historique, Produit.type)
            .all()
        )
        current_month_quantity = 0
        current_month_revenue = 0
        for record, product_type in current_month_records:
            if record.montant is not None:
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                current_month_quantity += quantity
                current_month_revenue += float(record.montant or 0)

        revenue_percent_change = (
            ((current_month_revenue - prev_month_revenue) / prev_month_revenue * 100)
            if prev_month_revenue else 100 if current_month_revenue else 0
        )

        response = {
            'duree_id': duree_id,
            'product_name': product.name if product else 'Unknown',
            'product_type': product.type,
            'current_stock': current_quantity,
            'prix_achat': float(prix_achat),
            'prix_1': float(duree.prix_1 or 0),
            'prix_2': float(duree.prix_2 or 0),
            'prix_3': float(duree.prix_3 or 0),
            'statistics': {
                'total_quantity_sold': float(total_quantity_sold),
                'total_revenue': float(total_revenue),
                'total_cost': float(total_cost),
                'profit': profit,
                'remaining_quantity': float(current_quantity),
                'sales_quantity': float(total_quantity_sold),
                'revenue_percent_change': float(revenue_percent_change),
                'monthly_breakdown_last_month': monthly_last_month,
                'custom_period': custom_period,
                'yearly_breakdown': yearly_sales_data,
                'top_users_last_month': top_users_last_month,
                'top_users_custom': top_users_custom,
                'annual_user_stats': annual_user_stats,
                'user_yearly_stats': user_yearly_stats_data
            }
        }

        return jsonify(response), 200
    except Exception as e:
        logging.error(f"Error in get_duree_statistics: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@statistics_bp.route('/user/<int:user_id>/statistics', methods=['GET'])
def get_user_statistics(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": f"User with id {user_id} not found"}), 404

        start_date = request.args.get('start_date', default=None, type=str)
        end_date = request.args.get('end_date', default=None, type=str)

        try:
            start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
            end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.utcnow()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

        # Check user role
        is_admin = user.role.lower() in ['admin', 'manager']
        user_dict = {u.id: u for u in User.query.all()}
        subordinates = get_subordinate_ids(user_id, user_dict) if is_admin else []

        # Base query for the user's sales
        base_query = Historique.query.join(
            Produit, Historique.produit == Produit.name
        ).filter(Historique.user_id == user_id)
        
        if start:
            base_query = base_query.filter(Historique.date >= func.cast(start, db.Date))
        if end:
            base_query = base_query.filter(Historique.date <= func.cast(end, db.Date))

        history_records = base_query.with_entities(Historique, Produit.type).all()

        total_quantity_sold = 0
        total_revenue = 0
        total_cost = 0
        product_stats = {}
        
        for record, product_type in history_records:
            if record.montant is not None:
                product = Produit.query.filter_by(name=record.produit).first()
                stock = Stock.query.filter_by(
                    produit_id=product.id if product else None,
                    duree=record.duree.strip().lower()
                ).first()
                prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
                
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                total_quantity_sold += quantity
                revenue = float(record.montant or 0)
                total_revenue += revenue
                total_cost += quantity * prix_achat
                
                product_key = f"{record.produit}_{record.duree}"
                if product_key not in product_stats:
                    product_stats[product_key] = {
                        'product_name': record.produit,
                        'duree': record.duree,
                        'quantity': 0,
                        'revenue': 0,
                        'cost': 0,
                        'profit': 0
                    }
                product_stats[product_key]['quantity'] += quantity
                product_stats[product_key]['revenue'] += revenue
                product_stats[product_key]['cost'] += quantity * prix_achat
                product_stats[product_key]['profit'] += float(revenue - (quantity * prix_achat)) if prix_achat > 0 else 0.0

        total_profit = float(total_revenue - total_cost) if total_cost else 0.0

        # Last month statistics (from start of current month)
        current_date = datetime.utcnow()
        last_month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_query = Historique.query.join(
            Produit, Historique.produit == Produit.name
        ).filter(
            Historique.user_id == user_id,
            Historique.date >= func.cast(last_month_start, db.Date),
            Historique.date <= func.cast(current_date, db.Date)
        ).with_entities(Historique, Produit.type)
        
        last_month_records = last_month_query.all()
        last_month_quantity = 0
        last_month_revenue = 0
        last_month_cost = 0
        last_month_daily = {}
        last_month_product_stats = {}
        
        for record, product_type in last_month_records:
            product = Produit.query.filter_by(name=record.produit).first()
            stock = Stock.query.filter_by(
                produit_id=product.id if product else None,
                duree=record.duree.strip().lower()
            ).first()
            prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
            quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
            revenue = float(record.montant or 0)
            date_key = record.date.strftime('%Y-%m-%d')
            last_month_quantity += quantity
            last_month_revenue += revenue
            last_month_cost += quantity * prix_achat
            
            if date_key not in last_month_daily:
                last_month_daily[date_key] = {'quantity': 0, 'revenue': 0, 'profit': 0}
            last_month_daily[date_key]['quantity'] += quantity
            last_month_daily[date_key]['revenue'] += revenue
            last_month_daily[date_key]['profit'] += float(revenue - (quantity * prix_achat)) if revenue else 0.0

            product_key = f"{record.produit}_{record.duree}"
            if product_key not in last_month_product_stats:
                last_month_product_stats[product_key] = {
                    'product_name': record.produit,
                    'duree': record.duree,
                    'quantity': 0,
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0
                }
            last_month_product_stats[product_key]['quantity'] += quantity
            last_month_product_stats[product_key]['revenue'] += revenue
            last_month_product_stats[product_key]['cost'] += quantity * prix_achat
            last_month_product_stats[product_key]['profit'] += float(revenue - (quantity * prix_achat)) if prix_achat > 0 else 0.0

        last_month_daily_data = [
            {
                'period': date_key,
                'quantity': float(data['quantity']),
                'revenue': float(data['revenue']),
                'profit': float(data['profit'])
            }
            for date_key, data in sorted(last_month_daily.items())
        ]

        last_month_profit = float(last_month_revenue - last_month_cost) if last_month_cost else 0.0
        last_month_product_stats_list = sorted(
            last_month_product_stats.values(),
            key=lambda x: x['revenue'],
            reverse=True
        )

        # Last year statistics (from start of current year)
        last_year_start = current_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        last_year_query = Historique.query.join(
            Produit, Historique.produit == Produit.name
        ).filter(
            Historique.user_id == user_id,
            Historique.date >= func.cast(last_year_start, db.Date),
            Historique.date <= func.cast(current_date, db.Date)
        ).with_entities(Historique, Produit.type)
        
        last_year_records = last_year_query.all()
        last_year_quantity = 0
        last_year_revenue = 0
        last_year_cost = 0
        last_year_monthly = {}
        last_year_product_stats = {}
        
        for record, product_type in last_year_records:
            product = Produit.query.filter_by(name=record.produit).first()
            stock = Stock.query.filter_by(
                produit_id=product.id if product else None,
                duree=record.duree.strip().lower()
            ).first()
            prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
            quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
            revenue = float(record.montant or 0)
            month_key = record.date.strftime('%Y-%m')
            last_year_quantity += quantity
            last_year_revenue += revenue
            last_year_cost += quantity * prix_achat
            
            if month_key not in last_year_monthly:
                last_year_monthly[month_key] = {'quantity': 0, 'revenue': 0, 'profit': 0}
            last_year_monthly[month_key]['quantity'] += quantity
            last_year_monthly[month_key]['revenue'] += revenue
            last_year_monthly[month_key]['profit'] += float(revenue - (quantity * prix_achat)) if revenue else 0.0

            product_key = f"{record.produit}_{record.duree}"
            if product_key not in last_year_product_stats:
                last_year_product_stats[product_key] = {
                    'product_name': record.produit,
                    'duree': record.duree,
                    'quantity': 0,
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0
                }
            last_year_product_stats[product_key]['quantity'] += quantity
            last_year_product_stats[product_key]['revenue'] += revenue
            last_year_product_stats[product_key]['cost'] += quantity * prix_achat
            last_year_product_stats[product_key]['profit'] += float(revenue - (quantity * prix_achat)) if prix_achat > 0 else 0.0

        last_year_monthly_data = [
            {
                'period': month_key,
                'quantity': float(data['quantity']),
                'revenue': float(data['revenue']),
                'profit': float(data['profit'])
            }
            for month_key, data in sorted(last_year_monthly.items())
        ]

        last_year_profit = float(last_year_revenue - last_year_cost) if last_year_cost else 0.0
        last_year_product_stats_list = sorted(
            last_year_product_stats.values(),
            key=lambda x: x['revenue'],
            reverse=True
        )

        # Hierarchical stats (only for admins)
        hierarchical_stats_all_time = []
        hierarchical_stats_last_month = []
        hierarchical_stats_last_year = []
        if is_admin:
            for sub_id in subordinates:
                sub_user = user_dict.get(sub_id)
                if not sub_user:
                    continue

                # All-time subordinate stats
                sub_query_all = Historique.query.join(
                    Produit, Historique.produit == Produit.name
                ).filter(Historique.user_id == sub_id)
                if start:
                    sub_query_all = sub_query_all.filter(Historique.date >= func.cast(start, db.Date))
                if end:
                    sub_query_all = sub_query_all.filter(Historique.date <= func.cast(end, db.Date))
                sub_records_all = sub_query_all.with_entities(Historique, Produit.type).all()
                sub_quantity_all = 0
                sub_revenue_all = 0
                sub_cost_all = 0
                for record, product_type in sub_records_all:
                    product = Produit.query.filter_by(name=record.produit).first()
                    stock = Stock.query.filter_by(
                        produit_id=product.id if product else None,
                        duree=record.duree.strip().lower()
                    ).first()
                    prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
                    quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                    sub_quantity_all += quantity
                    sub_revenue_all += float(record.montant or 0)
                    sub_cost_all += quantity * prix_achat

                hierarchical_stats_all_time.append({
                    'user_id': sub_id,
                    'user_name': sub_user.nom,
                    'quantity_sold': float(sub_quantity_all),
                    'revenue': float(sub_revenue_all),
                    'profit': float(sub_revenue_all - sub_cost_all) if sub_cost_all else 0.0,
                    'subordinate_count': len(get_subordinate_ids(sub_id, user_dict)),
                    'role': sub_user.role
                })

                # Last month subordinate stats
                sub_query_month = Historique.query.join(
                    Produit, Historique.produit == Produit.name
                ).filter(
                    Historique.user_id == sub_id,
                    Historique.date >= func.cast(last_month_start, db.Date),
                    Historique.date <= func.cast(current_date, db.Date)
                )
                sub_records_month = sub_query_month.with_entities(Historique, Produit.type).all()
                sub_quantity_month = 0
                sub_revenue_month = 0
                sub_cost_month = 0
                for record, product_type in sub_records_month:
                    product = Produit.query.filter_by(name=record.produit).first()
                    stock = Stock.query.filter_by(
                        produit_id=product.id if product else None,
                        duree=record.duree.strip().lower()
                    ).first()
                    prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
                    quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                    sub_quantity_month += quantity
                    sub_revenue_month += float(record.montant or 0)
                    sub_cost_month += quantity * prix_achat

                hierarchical_stats_last_month.append({
                    'user_id': sub_id,
                    'user_name': sub_user.nom,
                    'quantity_sold': float(sub_quantity_month),
                    'revenue': float(sub_revenue_month),
                    'profit': float(sub_revenue_month - sub_cost_month) if sub_cost_month else 0.0,
                    'subordinate_count': len(get_subordinate_ids(sub_id, user_dict)),
                    'role': sub_user.role
                })

                # Last year subordinate stats
                sub_query_year = Historique.query.join(
                    Produit, Historique.produit == Produit.name
                ).filter(
                    Historique.user_id == sub_id,
                    Historique.date >= func.cast(last_year_start, db.Date),
                    Historique.date <= func.cast(current_date, db.Date)
                )
                sub_records_year = sub_query_year.with_entities(Historique, Produit.type).all()
                sub_quantity_year = 0
                sub_revenue_year = 0
                sub_cost_year = 0
                for record, product_type in sub_records_year:
                    product = Produit.query.filter_by(name=record.produit).first()
                    stock = Stock.query.filter_by(
                        produit_id=product.id if product else None,
                        duree=record.duree.strip().lower()
                    ).first()
                    prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
                    quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                    sub_quantity_year += quantity
                    sub_revenue_year += float(record.montant or 0)
                    sub_cost_year += quantity * prix_achat

                hierarchical_stats_last_year.append({
                    'user_id': sub_id,
                    'user_name': sub_user.nom,
                    'quantity_sold': float(sub_quantity_year),
                    'revenue': float(sub_revenue_year),
                    'profit': float(sub_revenue_year - sub_cost_year) if sub_cost_year else 0.0,
                    'subordinate_count': len(get_subordinate_ids(sub_id, user_dict)),
                    'role': sub_user.role
                })

        sorted_product_stats = sorted(
            product_stats.values(),
            key=lambda x: x['revenue'],
            reverse=True
        )

        response = {
            'user_id': user_id,
            'user_name': user.nom,
            'role': user.role,
            'total_subordinates': len(subordinates) if is_admin else 0,
            'statistics': {
                'all_time': {
                    'quantity_sold': float(total_quantity_sold),
                    'revenue': float(total_revenue),
                    'profit': total_profit,
                    'products': sorted_product_stats,
                    'hierarchical_stats': sorted(hierarchical_stats_all_time, key=lambda x: x['revenue'], reverse=True) if is_admin else []
                },
                'last_month': {
                    'quantity_sold': float(last_month_quantity),
                    'revenue': float(last_month_revenue),
                    'profit': last_month_profit,
                    'daily_breakdown': last_month_daily_data,
                    'products': last_month_product_stats_list,
                    'hierarchical_stats': sorted(hierarchical_stats_last_month, key=lambda x: x['revenue'], reverse=True) if is_admin else []
                },
                'last_year': {
                    'quantity_sold': float(last_year_quantity),
                    'revenue': float(last_year_revenue),
                    'profit': last_year_profit,
                    'monthly_breakdown': last_year_monthly_data,
                    'products': last_year_product_stats_list,
                    'hierarchical_stats': sorted(hierarchical_stats_last_year, key=lambda x: x['revenue'], reverse=True) if is_admin else []
                }
            }
        }

        return jsonify(response), 200
    except Exception as e:
        logging.error(f"Error in get_user_statistics: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    

@statistics_bp.route('/user/<int:user_id>/subordinates', methods=['GET'])
def get_user_subordinates(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": f"User with id {user_id} not found"}), 404

        # Check if user is a revendeur; if so, return empty subordinates
        if user.role.lower() not in ['admin', 'manager']:
            return jsonify({
                'user_id': user_id,
                'user_name': user.nom,
                'subordinates': [],
                'total': 0,
                'page': 1,
                'per_page': 20,
                'total_pages': 0
            }), 200

        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=20, type=int)

        subordinates = User.query.filter_by(responsable=user_id).all()
        subordinate_stats = []
        
        for sub in subordinates:
            sub_query = Historique.query.join(
                Produit, Historique.produit == Produit.name
            ).filter(Historique.user_id == sub.id).with_entities(Historique, Produit.type)
            
            sub_quantity = 0
            sub_revenue = 0
            sub_cost = 0
            
            for record, product_type in sub_query.all():
                product = Produit.query.filter_by(name=record.produit).first()
                stock = Stock.query.filter_by(
                    produit_id=product.id if product else None,
                    duree=record.duree.strip().lower()
                ).first()
                prix_achat = float(stock.prix_achat) if stock and stock.prix_achat is not None and isinstance(stock.prix_achat, (int, float)) else 0.0
                quantity = len([code.strip() for code in record.codes.split(',') if code.strip()]) if product_type == 'code' and record.codes else 1
                sub_quantity += quantity
                sub_revenue += float(record.montant or 0)
                sub_cost += quantity * prix_achat

            subordinate_stats.append({
                'user_id': sub.id,
                'user_name': sub.nom,
                'email': sub.email,
                'telephone': sub.telephone,
                'niveau': sub.niveau,
                'role': sub.role,
                'subordinate_count': User.query.filter_by(responsable=sub.id).count(),
                'quantity_sold': float(sub_quantity),
                'revenue': float(sub_revenue),
                'profit': float(sub_revenue - sub_cost) if sub_cost else 0.0
            })

        sorted_subordinates = sorted(subordinate_stats, key=lambda x: x['revenue'], reverse=True)
        
        total = len(sorted_subordinates)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_subordinates = sorted_subordinates[start:end]

        return jsonify({
            'user_id': user_id,
            'user_name': user.nom,
            'subordinates': paginated_subordinates,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }), 200
    except Exception as e:
        logging.error(f"Error in get_user_subordinates: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500