import os
import time
import random
import json
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURACIÓN DE GEMINI ---
# Obtiene la API KEY desde las variables de entorno de Render
API_KEY = os.environ.get("API_KEY_GEMINI")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def analizar_con_gemini(marca, descripcion):
    """Usa IA para sugerir clases de Niza y evaluar riesgo"""
    prompt = f"""
    Eres un experto en Propiedad Industrial en México. Analiza:
    Marca: {marca}
    Giro del negocio: {descripcion}
    
    TAREAS:
    1. Sugiere las 2 o 3 Clases de Niza más probables.
    2. Evalúa la viabilidad de registro (0-100) considerando si el nombre es genérico o descriptivo.
    3. Dame una breve nota técnica para el ejecutivo legal.
    
    Responde estrictamente en formato JSON con esta estructura:
    {{
      "viabilidad": 85,
      "clases": ["Clase X: razón breve", "Clase Y: razón breve"],
      "nota": "Tu comentario técnico aquí"
    }}
    """
    try:
        response = model.generate_content(prompt)
        # Limpiamos la respuesta para obtener solo el JSON
        text_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text_response)
    except Exception as e:
        print(f"Error en Gemini: {e}")
        return {
            "viabilidad": 50, 
            "clases": ["Error al obtener clases"], 
            "nota": "No se pudo conectar con el motor de IA."
        }

# --- CONFIGURACIÓN DEL ROBOT (SELENIUM PARA DOCKER) ---
def buscar_en_marcanet(marca):
    """Abre un navegador invisible y consulta disponibilidad en IMPI"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Modo invisible
    chrome_options.add_argument("--no-sandbox") # Necesario para contenedores
    chrome_options.add_argument("--disable-dev-shm-usage") # Evita falta de memoria
    chrome_options.add_argument("--disable-gpu")
    
    # RUTA CRÍTICA PARA DOCKER: Donde se instala Chrome en la imagen de Linux
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    driver = None
    try:
        # En Selenium 4 con Docker, no necesitamos descargar el driver manualmente
        # si Chrome está instalado en el sistema.
        driver = webdriver.Chrome(options=chrome_options)
        
        url = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqDenominacionCompleto.pgi"
        driver.get(url)
        
        # Espera a que el campo de búsqueda aparezca
        input_busqueda = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "denominacion"))
        )
        
        # Simular escritura humana
        for letra in marca:
            input_busqueda.send_keys(letra)
            time.sleep(random.uniform(0.1, 0.2))
            
        btn_buscar = driver.find_element(By.ID, "btnBuscar")
        btn_buscar.click()
        
        # Esperar a que la página cargue los resultados
        time.sleep(random.uniform(4, 6))
        
        # Verificar si aparece el mensaje de "No se encontraron registros"
        if "No se encontraron registros" in driver.page_source:
            return "DISPONIBLE"
        else:
            return "OCUPADA"
            
    except Exception as e:
        print(f"Error en el robot Selenium: {e}")
        return "ERROR_CONEXION"
    finally:
        if driver:
            driver.quit()

# --- RUTAS DE LA APLICACIÓN WEB ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    data = request.json
    marca = data.get('marca')
    descripcion = data.get('descripcion')

    if not marca or not descripcion:
        return jsonify({"error": "Faltan datos"}), 400

    # 1. Obtener análisis de inteligencia de Gemini
    resultado_final = analizar_con_gemini(marca, descripcion)
    
    # 2. Consultar disponibilidad real en IMPI con el robot
    disponibilidad = buscar_en_marcanet(marca)
    
    # 3. Ajustar lógica de viabilidad según la búsqueda real
    if disponibilidad == "OCUPADA":
        resultado_final['viabilidad'] = random.randint(0, 10)
        resultado_final['nota'] = "¡ALERTA! Se encontraron registros idénticos en el IMPI. El riesgo de rechazo es muy alto."
    elif disponibilidad == "ERROR_CONEXION":
        resultado_final['nota'] = "Nota: El IMPI no respondió a la consulta técnica, pero aquí está el análisis de la IA."

    return jsonify(resultado_final)

if __name__ == '__main__':
    # Render usa el puerto 10000 por defecto para servicios Docker
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
