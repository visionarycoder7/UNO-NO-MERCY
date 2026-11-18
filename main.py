import uvicorn
from backend.app.config import HOST, PORT

if __name__ == "__main__":
    print(f"🔥 Starting UNO Show 'Em No Mercy Server on http://{HOST}:{PORT} ...")
    uvicorn.run(
        "backend.app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        reload_excludes=["*.db", "*.sqlite*", "*.log", "uno_no_mercy.db*", "scratch_*"]
    )
