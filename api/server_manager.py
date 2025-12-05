# api/server_manager.py

import threading
import time
import os
import subprocess
import signal
from multiprocessing import Process, Queue # <--- REQUISITO: Procesos y Colas
from gpiozero import LED, Button, Device
from gpiozero.pins.mock import MockFactory

# --- CONFIGURACIÓN ---
PIN_LED_SCRIPT_ACTIVO = 16
PIN_LED_SERVER_STATUS = 17
PIN_BUTTON = 26

SERVER_JAR = "paper-1.21.10-113.jar"
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
MINECRAFT_SERVER_PATH = os.path.join(SERVER_DIR, "..", "..", "minecraft_server", SERVER_JAR)
MINECRAFT_CWD = os.path.join(SERVER_DIR, "..", "..", "minecraft_server")
SERVER_COMMAND = ["java", "-Xmx512M", "-Xms128M", "-jar", MINECRAFT_SERVER_PATH, "nogui"]

# --- VARIABLES GLOBALES ---
server_process = None
server_start_time = None
led_activo = None
button = None
GPIO_OK = False

# --- REQUISITO: COLA DE COMUNICACIÓN ENTRE PROCESOS ---
# Usaremos esta cola para mandar mensajes "ON", "OFF", "BLINK" al Proceso 2
led_queue = Queue()

# ==============================================================================
#  PROCESO 2: CONTROLADOR VISUAL INDEPENDIENTE (Process)
#  (Cumple el requisito de: "Al menos 2 procesos implementados")
# ==============================================================================
def led_process_target(queue, pin_led):
    """
    Este es un PROCESO separado.
    Su única misión es controlar el LED de estado sin bloquear al resto.
    """
    # IMPORTANTE: En un nuevo proceso, hay que re-inicializar el objeto LED
    # porque los objetos de hardware no pasan de un proceso a otro.
    try:
        my_led = LED(pin_led)
    except:
        Device.pin_factory = MockFactory()
        my_led = LED(pin_led)
        
    print(f"PROCESS [PID {os.getpid()}]: Iniciado controlador de luces.")
    
    current_mode = "OFF" # Modos: OFF, ON, BLINK
    
    while True:
        # 1. Mirar si hay órdenes nuevas en la cola (sin bloquear)
        if not queue.empty():
            command = queue.get()
            current_mode = command

        # 2. Ejecutar la acción según el modo
        if current_mode == "ON":
            my_led.on()
            time.sleep(0.1)
        elif current_mode == "OFF":
            my_led.off()
            time.sleep(0.1)
        elif current_mode == "BLINK":
            my_led.toggle()
            time.sleep(0.5) # Velocidad del parpadeo
            
# ==============================================================================
#  HILO 2: LECTOR DE CONSOLA (Thread)
#  (Cumple el requisito de: "Al menos 2 hilos implementados")
# ==============================================================================
def console_reader_thread(proc):
    """
    Este HILO lee lo que escupe el servidor de Minecraft para detectar
    cuándo ha terminado de cargar ("Done!").
    """
    print("THREAD: Iniciando monitor de consola...")
    while True:
        # Leemos línea a línea lo que dice Java
        output = proc.stdout.readline()
        
        # Si el proceso muere, salimos
        if output == '' and proc.poll() is not None:
            break
            
        if output:
            line = output.strip()
            # print(f"MINECRAFT: {line}") # Descomentar para depurar
            
            # Si Java dice "Done!", es que ya cargó el mundo
            if "Done" in line:
                print("THREAD: ¡Servidor cargado al 100%!")
                # REQUISITO: Sincronización (Hilo avisa a Proceso vía Cola)
                led_queue.put("ON") 

# ==============================================================================
#  LÓGICA PRINCIPAL (PROCESO 1)
# ==============================================================================

def setup_gpio_main():
    """Configura el botón y el LED de sistema (solo para el proceso principal)."""
    global led_activo, button, GPIO_OK
    try:
        led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
        button = Button(PIN_BUTTON)
        button.when_pressed = toggle_server_interface
        led_activo.on()
        GPIO_OK = True
    except:
        Device.pin_factory = MockFactory()
        led_activo = LED(PIN_LED_SCRIPT_ACTIVO)
        button = Button(PIN_BUTTON)
        button.when_pressed = toggle_server_interface
        GPIO_OK = True

def init_system():
    """Arranca todo el sistema."""
    setup_gpio_main()
    
    # 1. ARRANCAR EL PROCESO DEL LED (Proceso Secundario)
    p_led = Process(target=led_process_target, args=(led_queue, PIN_LED_SERVER_STATUS))
    p_led.daemon = True # Se cierra si el principal se cierra
    p_led.start()
    
    print(f"MAIN [PID {os.getpid()}]: Sistema iniciado.")

def start_server():
    global server_process, server_start_time
    
    if get_server_status() == "running": return True
    
    print("MAIN: Iniciando servidor...")
    
    # 1. Mandar mensaje a la cola para que el OTRO PROCESO parpadee
    led_queue.put("BLINK")
    
    try:
        server_process = subprocess.Popen(
            SERVER_COMMAND, cwd=MINECRAFT_CWD, 
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        server_start_time = time.time()
        
        # 2. ARRANCAR EL HILO DE MONITORIZACIÓN (Hilo Secundario)
        monitor = threading.Thread(target=console_reader_thread, args=(server_process,))
        monitor.daemon = True
        monitor.start()
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        led_queue.put("OFF")
        return False

def stop_server():
    global server_process, server_start_time
    
    if get_server_status() == "stopped": return True
    
    print("MAIN: Deteniendo servidor...")
    led_queue.put("BLINK") # Parpadear mientras cierra
    
    try:
        if server_process:
            server_process.stdin.write("stop\n")
            server_process.stdin.flush()
            # Esperamos un poco a que guarde
            try:
                server_process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server_process.terminate()
        
    except:
        if server_process: server_process.terminate()
        
    server_process = None
    server_start_time = None
    led_queue.put("OFF") # Apagar LED cuando termine
    return True

def get_server_status():
    if server_process and server_process.poll() is None:
        return "running"
    return "stopped"

def get_uptime():
    if server_start_time and get_server_status() == "running":
        return int(time.time() - server_start_time)
    return 0

def toggle_server_interface():
    """Función para el botón físico"""
    print("🔘 Botón presionado.")
    if get_server_status() == "stopped":
        start_server()
    else:
        stop_server()

def cleanup():
    if GPIO_OK and led_activo: 
        led_activo.close()

# Si ejecutas este archivo directamente (para pruebas manuales)
if __name__ == "__main__":
    init_system()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        cleanup()