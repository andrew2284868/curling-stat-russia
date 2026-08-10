import uvicorn
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    port_raw = os.environ.get("PORT", "8000")
    try:
        port = int(port_raw)
    except Exception:
        port = 8000

    print("=======================================================")
    print(f" Curling Analytics & Rankings Platform (2016-2026)")
    print(f" Running on http://0.0.0.0:{port}")
    print("=======================================================")

    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=False)
