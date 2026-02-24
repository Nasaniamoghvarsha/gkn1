---
description: How to initialize and run the GKN RAG system for the first time.
---

// turbo-all
1. Install Python dependencies:
   `pip install -r requirements.txt`

2. Setup the database schema:
   `$env:PYTHONPATH="."; python src/setup_db.py`

3. Start the FastAPI backend:
   `python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001`

4. (New Window) Setup the IDE Extension:
   `cd gkn-ide-extension; npm install; npm run compile`

5. Verify health:
   `python gkn.py health`
