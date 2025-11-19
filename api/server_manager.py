# api/server_manager.py (Usando gpiozero)

from gpiozero import LED, Button
import subprocess
import signal
import os
import time

# --- CONFIGURACIÓN ---
# Nota: gpiozero usa el esquema BCM directamente, como en RPi.GPIO
PIN_LED_SCRIPT_ACTIVO = 16
PIN_LED_SERVER_STATUS = 17
PIN_BUTTON = 26

SERVER_JAR = "paper-1.21.10-113.jar"

# --- AJUSTE CLAVE DE RUTA (el mismo de antes) ---
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
MINECRAFT_SERVER_PATH = os.path.join(SERVER_DIR, "..", "..", "minecraft_server", SERVER_JAR)
MINECRAFT_CWD = os.path.join(SERVER_DIR, "..", "..", "minecraft_server")
SERVER_COMMAND = ["java", "-Xmx512M", "-Xms128M", "-jar", MINECRAFT_SERVER_PATH, "nogui"]

# Variables Globales
server_process = None
server_start_time = None

# Objetos GPIOzero
try:
    led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
    led_status = LED(PIN_LED_SERVER_STATUS)
    button = Button(PIN_BUTTON)
    GPIO_OK = True
except Exception as e:
    # Captura errores si no está en una Pi o no tiene permisos, PERO
    # con gpiozero y sudo la probabilidad es menor.
    print(f"Advertencia: Fallo al inicializar GPIO (gpiozero). {e}")
    GPIO_OK = False


def init_gpio():
    """Inicializa los LEDs de estado (usando gpiozero)."""
    if GPIO_OK:
        try:
            led_activo.on()
            led_status.off()
            print(f"GPIO inicializado (gpiozero). LED activo (Pin {PIN_LED_SCRIPT_ACTIVO}) ON.")
        except Exception as e:
            print(f"Advertencia: Fallo al encender LEDs. {e}")
    else:
        print("GPIO NO DISPONIBLE. Ejecutar la API sin control de hardware.")


def cleanup_gpio():
    """Limpia los pines GPIO al cerrar (usando gpiozero)."""
    if GPIO_OK:
        try:
            led_activo.off()
            led_status.off()
            print("GPIO limpiado y LEDs apagados.")
        except Exception as e:
            print(f"Advertencia: Fallo al limpiar GPIO. {e}")


# --- Funciones de control de Servidor (Sin cambios de lógica) ---

def get_server_status():
    global server_process
    if server_process and server_process.poll() is None:
        return "running"
    return "stopped"


def start_server():
    """Inicia el servidor de Minecraft."""
    global server_process, server_start_time
    if get_server_status() == "stopped":
        print("Iniciando servidor de Minecraft...")
        try:
            # Primero, comprueba si Java está instalado
            if not is_java_installed():
                print("ERROR: Java no encontrado. Asegúrese de que 'java' está en el PATH.")
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
            if GPIO_OK:
                led_status.on()  # Enciende el LED de estado
            return True
        except Exception as e:
            print(f"ERROR al iniciar servidor: {e}")
            return False
    return False


def stop_server():
    """Detiene el servidor de Minecraft."""
    global server_process, server_start_time
    if get_server_status() == "running":
        print("Deteniendo servidor de Minecraft...")
        try:
            server_process.stdin.write("stop\n")
            server_process.stdin.flush()
            server_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            print("El servidor no se detuvo, forzando terminación.")
            server_process.terminate()
            server_process.wait()
        except Exception as e:
            print(f"Error al intentar detener: {e}")

        server_process = None
        server_start_time = None
        if GPIO_OK:
            led_status.off()  # Apaga el LED de estado
        return True
    return False


def get_uptime():
    if server_start_time:
        return int(time.time() - server_start_time)
    return 0


# Función para añadir una comprobación robusta de Java (debido a tu problema previo)
def is_java_installed():
    try:
        subprocess.run(['java', '-version'], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# Inicialización
init_gpio()

# Limpieza al terminar
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_gpio())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_gpio())