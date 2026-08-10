import uvicorn
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"=======================================================")
    print(f" Curling Analytics & Rankings Platform (2016-2026)")
    print(f" Dashboard running at: http://localhost:{port}")
    print(f" API documentation at: http://localhost:{port}/docs")
    print(f"=======================================================")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
