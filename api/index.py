# language: Python 3.11+, file: api/index.py
# *Vercel serverless entry point — Flask app expose.*

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import app
