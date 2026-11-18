import uvicorn
from backend.app.main import app
from backend.app.config import HOST, PORT

if __name__ == "__main__":
    print(f"🔥 Starting UNO Show 'Em No Mercy Server on http://{HOST}:{PORT} ...")
    uvicorn.run("backend.app.main:app", host=HOST, port=PORT, reload=True)
