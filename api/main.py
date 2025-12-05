# api/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import server_manager

# --- CICLO DE VIDA (LIFESPAN) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # AL INICIAR: Arrancamos el proceso de los LEDs y configuramos GPIO
    print("🚀 Arrancando Sistema Multiproceso...")
    server_manager.init_system()
    
    yield # Aquí la API está funcionando
    
    # AL APAGAR
    print("👋 Cerrando sistema...")
    server_manager.cleanup()

app = FastAPI(lifespan=lifespan)

# --- ENDPOINTS ---
@app.get("/status")
def get_status():
    return {
        "status": server_manager.get_server_status(), 
        "uptime_seconds": server_manager.get_uptime()
    }

@app.post("/start")
def start():
    server_manager.start_server()
    return {"status": "processing", "message": "Iniciando..."}

@app.post("/stop")
def stop():
    server_manager.stop_server()
    return {"status": "processing", "message": "Deteniendo..."}

# Servir Frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)