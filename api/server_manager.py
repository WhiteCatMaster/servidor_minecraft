# api/server_manager.py

from gpiozero import LED, Button, Device
from gpiozero.pins.mock import MockFactory
import subprocess
import signal
import os
import time
import threading # IMPORTANTE: Para evitar choques entre botón y web

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

# CANDADO DE SEGURIDAD
# Evita que el botón y la web intenten encender el servidor al mismo milisegundo
server_lock = threading.Lock()

# --- INICIALIZACIÓN ROBUSTA DE GPIO ---
led_activo = None
led_status = None
button = None
GPIO_OK = False

def setup_gpio_objects():
    """Configura los objetos GPIO con fallback a simulación."""
    global led_activo, led_status, button, GPIO_OK
    
    try:
        # Intento 1: Hardware Real
        led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
        led_status = LED(PIN_LED_SERVER_STATUS)
        button = Button(PIN_BUTTON)
        GPIO_OK = True
        print("✅ Hardware GPIO detectado.")
    except Exception as e:
        print(f"⚠️  No se detectó hardware GPIO nativo: {e}")
        print("🔄 Activando MODO SIMULACIÓN (MockFactory)...")
        try:
            Device.pin_factory = MockFactory()
            led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
            led_status = LED(PIN_LED_SERVER_STATUS)
            button = Button(PIN_BUTTON)
            GPIO_OK = True # Marcamos como OK para que la lógica funcione (aunque sea simulada)
            print("✅ Simulación cargada correctamente.")
        except Exception as e2:
            print(f"❌ Error crítico GPIO: {e2}")
            GPIO_OK = False

# Llamamos a la configuración de objetos al importar
setup_gpio_objects()

# --- Funciones de control de Servidor ---

def get_server_status():
    global server_process
    # Comprobamos si el proceso existe y sigue vivo (poll es None si sigue vivo)
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
    """Inicia el servidor de Minecraft (Thread-safe)."""
    global server_process, server_start_time
    
    # Usamos el candado para que nadie más entre aquí mientras procesamos
    with server_lock:
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
    """Detiene el servidor de Minecraft (Thread-safe)."""
    global server_process, server_start_time
    
    with server_lock:
        if get_server_status() == "stopped":
            print("El servidor ya está detenido.")
            return True

        print("Deteniendo servidor de Minecraft...")
        try:
            if server_process:
                # Enviamos comando stop a la consola de Minecraft
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
    if server_start_time and get_server_status() == "running":
        return int(time.time() - server_start_time)
    return 0

# --- LÓGICA DEL BOTÓN ---
def toggle_server_from_button():
    """Esta función se ejecuta al presionar el botón físico."""
    print("\n🔘 Botón presionado detectado.")
    
    # No necesitamos bloquear aquí porque start_server y stop_server ya tienen el candado
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
            
            # 2. Sincronizar LED de estado con el estado real del servidor
            if led_status:
                if get_server_status() == "running":
                    led_status.on()
                else:
                    led_status.off()

            # 3. VINCULAR EL BOTÓN A LA FUNCIÓN (MAGIA AQUÍ)
            if button:
                # when_pressed ejecuta la función en un hilo aparte
                button.when_pressed = toggle_server_from_button
                print(f"✅ Botón (Pin {PIN_BUTTON}) vinculado y escuchando...")
                
        except Exception as e:
            print(f"Advertencia GPIO: {e}")
    else:
        print("⚠️ Ejecutando sin control GPIO.")

def cleanup_gpio():
    """Apaga los LEDs al salir."""
    if GPIO_OK:
        try:
            if led_activo: led_activo.off()
            if led_status: led_status.off()
            print("GPIO limpiado.")
        except:
            pass

# Si ejecutas este archivo directamente (para pruebas)
if __name__ == "__main__":
    init_gpio()
    print("Modo prueba manual. Presiona CTRL+C para salir.")
    signal.pause()