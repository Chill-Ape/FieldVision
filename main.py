"""
Main entry point for FieldVision AI application
Uses the Flask app configured in app.py with database and routes
"""

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)