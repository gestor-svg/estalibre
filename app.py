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
API_KEY = os.environ.get("API_KEY_GEMINI")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def analizar_con_gemini(marca, descripcion):
    """Usa IA para sugerir clases de Niza y evaluar riesgo"""
    prompt = f"""
    Eres un experto en Propiedad Industrial en México. Analiza:
    Marca: {marca}
    Giro del negocio: {descripcion}
    
    Responde estrictamente en formato JSON:
    {{
      "viabilidad": 85,
      "clases": ["Clase X: razón"],
      "nota": "Tu comentario técnico"
    }}
    """
    try:
        response = model.generate_content(prompt)
        text_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text_response)
    except Exception as e:
        print(f"Error en Gemini: {e}")
        return {"viabilidad": 50, "clases": ["Error de IA"], "nota": "No se pudo conectar con la IA."}

# --- CONFIGURACIÓN DEL ROBOT (SELENIUM OPTIMIZADO PARA RENDER) ---
def buscar_en_marcanet(marca):
    """Consulta disponibilidad en IMPI con configuración de alto rendimiento"""
    chrome_options = Options()
    # Modo headless moderno y ultra-ligero
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Optimizaciones de red y carga
    chrome_options.add_argument("--proxy-server='direct://'")
    chrome_options.add_argument("--proxy-bypass-list=*")
    # Desactivar carga de imágenes para ahorrar RAM y tiempo
    chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # Limitar el tiempo de espera de carga de página a 25 segundos
        driver.set_page_load_timeout(25)
        
        url = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqDenominacionCompleto.pgi"
        driver.get(url)
        
        # Espera máxima de 10 segundos para encontrar el input
        wait = WebDriverWait(driver, 10)
        input_busqueda = wait.until(EC.presence_of_element_located((By.NAME, "denominacion")))
        
        # Envío rápido del texto
        input_busqueda.send_keys(marca)
        
        btn_buscar = driver.find_element(By.ID, "btnBuscar")
        btn_buscar.click()
        
        # Tiempo de espera optimizado para resultados (3 segundos es suficiente sin imágenes)
        time.sleep(3)
        
        # Búsqueda rápida en el código fuente
        page_source = driver.page_source
        if "No se encontraron registros" in page_source:
            return "DISPONIBLE"
        else:
            return "OCUPADA"
            
    except Exception as e:
        print(f"Error en el robot: {e}")
        return "ERROR_CONEXION"
    finally:
        if driver:
            driver.quit()

# --- RUTAS ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    data = request.json
    marca = data.get('marca')
    descripcion = data.get('descripcion')

    if not marca or not descripcion:
        return jsonify({"error": "Datos incompletos"}), 400

    # Ejecución de Gemini
    resultado_final = analizar_con_gemini(marca, descripcion)
    
    # Ejecución del Robot
    disponibilidad = buscar_en_marcanet(marca)
    
    # Lógica de negocio combinada
    if disponibilidad == "OCUPADA":
        resultado_final['viabilidad'] = 5
        resultado_final['nota'] = "¡ALERTA! El robot detectó registros idénticos en el IMPI. Registro no recomendado."
    elif disponibilidad == "ERROR_CONEXION":
        resultado_final['nota'] += " (El robot técnico falló, pero el análisis de IA fue exitoso)."

    return jsonify(resultado_final)

if __name__ == '__main__':
    # Puerto dinámico para Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
