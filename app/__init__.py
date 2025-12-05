"""Flask application factory."""

import os
from flask import Flask

def create_app() -> Flask:
    app = Flask(__name__, 
                template_folder="../templates",
                static_folder="../static")
    
    # Register blueprints
    from app.web.routes import bp
    app.register_blueprint(bp)
    
    return app
