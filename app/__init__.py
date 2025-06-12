from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO
import os

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object('app.config.config.Config')

    # CORS for frontend origins
    CORS(app, origins=[
        "http://95.216.112.177:5555",
        "http://95.216.112.177:82",
        "http://95.216.112.177:83",
        "http://localhost:3000"
    ], supports_credentials=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    socketio.init_app(app)

    # Import models
    from app.models.user import User
    from app.models.product import Produit
    from app.models.stock import Stock
    from app.models.boutique import Boutique
    from app.models.article import Article
    from app.models.duree_sans_stock import DureeSansStock
    from app.models.transaction_paye import TransactionPaye
    from app.models.transaction_impaye import TransactionImpaye
    from app.models.visible_item import VisibleItem
    from app.models.historique import Historique   # ✅ Add this line

    # Import routes
    from app.routes.categories import categories_bp
    from app.routes.sous_categories import sous_categories_bp
    from app.routes.applications import applications_bp
    from app.routes.produits import products_bp
    from app.routes.stocks import stocks_bp
    from app.routes.duree_sans_stock import duree_sans_stock_bp
    from app.routes.boutiques import boutiques_bp
    from app.routes.articles import articles_bp
    from app.routes.users import users_bp
    from app.routes.demande_solde import demande_solde_bp
    from app.routes.duree_avec_stock import duree_avec_stock_bp
    from app.routes.gest_messages import gest_message_bp
    from app.routes.transaction import transactions_bp
    from app.routes.visible_items import visible_bp
    # from app.routes.historique import historique_bp  # ✅ Uncomment once you create the routes

    # Register blueprints
    app.register_blueprint(gest_message_bp, url_prefix='/api/gest_message')
    app.register_blueprint(duree_avec_stock_bp, url_prefix='/api/duree_avec_stock')
    app.register_blueprint(demande_solde_bp, url_prefix='/api/demande_solde')
    app.register_blueprint(articles_bp, url_prefix='/api/article')
    app.register_blueprint(boutiques_bp, url_prefix='/api/gerer_boutique')
    app.register_blueprint(duree_sans_stock_bp, url_prefix='/api/Sans_stock')
    app.register_blueprint(stocks_bp, url_prefix='/api/stock')
    app.register_blueprint(products_bp, url_prefix='/api/product')
    app.register_blueprint(applications_bp, url_prefix='/api/applications')
    app.register_blueprint(categories_bp, url_prefix='/api/categories')
    app.register_blueprint(sous_categories_bp, url_prefix='/api/sous_categories')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    app.register_blueprint(visible_bp, url_prefix='/api/visible_items')
    # app.register_blueprint(historique_bp, url_prefix='/api/historique')  # ✅ Enable once route is ready

    return app
