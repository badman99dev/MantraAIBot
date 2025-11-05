# web_server.py

import os
from flask import Flask

app_flask = Flask(__name__)

@app_flask.route('/')
def hello_world(): 
    return "Xylon AI is alive and kicking!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)
