# api/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
import server_manager

# --- CICLO DE VIDA (LIFESPAN) ---
# Esto maneja qué pasa cuando la API se enciende y se apaga
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. AL INICIAR: Activamos los GPIO y el Botón
    print("🌐 Iniciando API y vinculando Botón Físico...")
    server_manager.init_gpio()
    
    yield # Aquí la API está funcionando y recibiendo peticiones
    
    # 2. AL APAGAR: Limpiamos los GPIO
    print("💤 Apagando API y liberando GPIO...")
    server_manager.cleanup_gpio()

# Crear la aplicación FastAPI con el ciclo de vida
app = FastAPI(lifespan=lifespan)

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
    # Como server_manager tiene un Lock, es seguro llamarlo desde la web
    success = server_manager.start_server()
    status = server_manager.get_server_status()
    message = "Server started successfully" if success else "Server is already running or error."
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

if __name__ == "__main__":
    # La API correrá en http://0.0.0.0:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)