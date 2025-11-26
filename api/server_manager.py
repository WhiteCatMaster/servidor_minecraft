# api/server_manager.py (Usando gpiozero)

from gpiozero import LED, Button, Device
from gpiozero.pins.mock import MockFactory  # Necesario para evitar el error de Pin Factory
import subprocess
import signal
import os
import time
import sys

# --- CONFIGURACIÓN ---
PIN_LED_SCRIPT_ACTIVO = 16
PIN_LED_SERVER_STATUS = 17
PIN_BUTTON = 26

SERVER_JAR = "paper-1.21.10-113.jar"

# --- RUTAS ---
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
MINECRAFT_SERVER_PATH = os.path.join(SERVER_DIR, "..", "..", "minecraft_server", SERVER_JAR)
MINECRAFT_CWD = os.path.join(SERVER_DIR, "..", "..", "minecraft_server")
SERVER_COMMAND = ["java", "-Xmx512M", "-Xms128M", "-jar", MINECRAFT_SERVER_PATH, "nogui"]

# Variables Globales
server_process = None
server_start_time = None

# --- INICIALIZACIÓN ROBUSTA DE GPIO ---
# Esto soluciona tu error "Unable to load any default pin factory"
led_activo = None
led_status = None
button = None
GPIO_OK = False

try:
    # Intento 1: Hardware Real
    led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
    led_status = LED(PIN_LED_SERVER_STATUS)
    button = Button(PIN_BUTTON)
    GPIO_OK = True
except Exception as e:
    print(f"⚠️  No se detectó hardware GPIO nativo: {e}")
    print("🔄 Activando MODO SIMULACIÓN (MockFactory)...")
    try:
        # Intento 2: Simulación (para que no crashee en PC o sin drivers)
        Device.pin_factory = MockFactory()
        led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
        led_status = LED(PIN_LED_SERVER_STATUS)
        button = Button(PIN_BUTTON)
        # Nota: GPIO_OK se queda en False para indicar que es simulado si quieres,
        # o True si quieres que la lógica funcione igual. Lo dejaremos True para probar la lógica.
        GPIO_OK = True 
        print("✅ Simulación cargada. El botón funcionará en lógica, pero no físicamente.")
    except Exception as e2:
        print(f"❌ Error crítico GPIO: {e2}")
        GPIO_OK = False

# --- Funciones de control de Servidor ---

def get_server_status():
    global server_process
    if server_process and server_process.poll() is None:
        return "running"
    return "stopped"

def is_java_installed():
    try:
        subprocess.run(['java', '-version'], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def start_server():
    """Inicia el servidor de Minecraft."""
    global server_process, server_start_time
    
    if get_server_status() == "running":
        print("El servidor ya está corriendo.")
        return True

    print("Iniciando servidor de Minecraft...")
    try:
        if not is_java_installed():
            print("ERROR: Java no encontrado.")
            return False

        server_process = subprocess.Popen(
            SERVER_COMMAND,
            cwd=MINECRAFT_CWD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        server_start_time = time.time()
        
        if GPIO_OK and led_status:
            led_status.on() # LED ON
            
        return True
    except Exception as e:
        print(f"ERROR al iniciar servidor: {e}")
        return False

def stop_server():
    """Detiene el servidor de Minecraft."""
    global server_process, server_start_time
    
    if get_server_status() == "stopped":
        print("El servidor ya está detenido.")
        return True

    print("Deteniendo servidor de Minecraft...")
    try:
        if server_process:
            server_process.stdin.write("stop\n")
            server_process.stdin.flush()
            # Esperamos hasta 30 segundos
            try:
                server_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                print("Forzando cierre...")
                server_process.terminate()
                server_process.wait()

        server_process = None
        server_start_time = None
        
        if GPIO_OK and led_status:
            led_status.off() # LED OFF
            
        return True
    except Exception as e:
        print(f"Error al detener: {e}")
        return False

def get_uptime():
    if server_start_time:
        return int(time.time() - server_start_time)
    return 0

# --- LÓGICA DEL BOTÓN ---
def toggle_server_from_button():
    """Esta función se ejecuta al presionar el botón físico."""
    print("\n🔘 Botón presionado detectado.")
    status = get_server_status()
    
    if status == "stopped":
        print("🔘 Acción: Encender servidor.")
        start_server()
    elif status == "running":
        print("🔘 Acción: Apagar servidor.")
        stop_server()

# --- GESTIÓN GPIO ---

def init_gpio():
    """Inicializa estado y vincula el botón."""
    if GPIO_OK:
        try:
            # 1. Encender LED de "Script Activo"
            if led_activo: 
                led_activo.on()
            
            # 2. Asegurar LED de estado apagado al inicio
            if led_status: 
                led_status.off()

            # 3. VINCULAR EL BOTÓN A LA FUNCIÓN
            if button:
                # when_pressed ejecuta la función automáticamente sin bloquear el código
                button.when_pressed = toggle_server_from_button
                print(f"✅ Botón (Pin {PIN_BUTTON}) vinculado correctamente.")
                
        except Exception as e:
            print(f"Advertencia GPIO: {e}")
    else:
        print("⚠️ Ejecutando sin control GPIO.")

def cleanup_gpio():
    """Apaga todo al salir."""
    if GPIO_OK:
        try:
            if led_activo: led_activo.off()
            if led_status: led_status.off()
            print("GPIO limpiado.")
        except:
            pass

# --- ARRANQUE ---

# Inicialización
init_gpio()

# Limpieza al terminar
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_gpio())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_gpio())

# Si ejecutas este archivo directamente (para pruebas), esto mantendrá el script vivo
# para que puedas pulsar el botón.
if __name__ == "__main__":
    print("Script server_manager corriendo en modo directo. Presiona CTRL+C para salir.")
    signal.pause()