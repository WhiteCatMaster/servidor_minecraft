# api/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import server_manager

# Crear la aplicación FastAPI
app = FastAPI()

# --- ENDPOINTS DE CONTROL DEL SERVIDOR ---

@app.get("/status")
def get_server_status():
    """Devuelve el estado actual y el uptime."""
    status = server_manager.get_server_status()
    uptime = server_manager.get_uptime()
    return {"status": status, "uptime_seconds": uptime}

@app.post("/start")
def api_start_server():
    """Inicia el servidor."""
    success = server_manager.start_server()
    status = server_manager.get_server_status()
    message = "Server started successfully" if success else "Server is already running."
    return {"message": message, "status": status}

@app.post("/stop")
def api_stop_server():
    """Detiene el servidor."""
    success = server_manager.stop_server()
    status = server_manager.get_server_status()
    message = "Server stopped successfully." if success else "Server was not running."
    return {"message": message, "status": status}

# --- SERVIR EL FRONTEND (STATIC FILES) ---

# Montar la carpeta 'frontend' para servir index.html
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

# Endpoint opcional para la raíz, aunque StaticFiles ya maneja el index.html
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    with open("frontend/index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    # La API correrá en http://0.0.0.0:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)