from flask_cors import CORS

def setup_cors(app):
    """Configure CORS for the Flask application"""
    cors = CORS(app)
    app.config['CORS_HEADERS'] = 'Content-Type'
    return cors
