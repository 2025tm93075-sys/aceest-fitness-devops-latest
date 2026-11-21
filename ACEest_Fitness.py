"""
ACEest Fitness & Gym - application entry point.

Author : Bandgar Omkar Sudhakar Sheetal (2025TM93075)

The WSGI object ``app`` is what Gunicorn serves in the container:
    gunicorn --bind 0.0.0.0:5000 ACEest_Fitness:app
For local development:
    python ACEest_Fitness.py
"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
