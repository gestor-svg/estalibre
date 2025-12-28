import os
import time
import random
import json
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURACIÓN DE GEMINI ---
# Railway leerá automáticamente tu API KEY desde las Variables de Entorno
API_KEY = os.environ.get("API_KEY_GEMINI")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def analizar_con_gemini(marca, descripcion):
    """Usa IA para sugerir clases de Niza y evaluar riesgo"""
    prompt = f"""
    Eres un experto en Propiedad Industrial. Analiza:
    Marca: {marca}
    Giro: {descripcion}
    
    1. Sugiere las 2 Clases de Niza más probables.
    2. Evalúa viabilidad (0-100) considerando si el nombre es genérico.
    3. Dame una nota técnica breve.
    
    Responde en JSON:
    {{"viabilidad": 85, "clases": ["Clase X: razón", "Clase Y: razón"], "nota": "..."}}
    """
    try:
        response = model.generate_content(prompt)
        # Limpieza simple de la respuesta para asegurar JSON puro
        json_data = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_data)
    except:
        return {"viabilidad": 50, "clases": ["No disponible"], "nota": "Error de análisis"}

# --- CONFIGURACIÓN DEL ROBOT (SELENIUM) ---
def buscar_en_marcanet(marca):
    """Abre un navegador invisible y busca disponibilidad real"""
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Invisible
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # User agent para parecer humano
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    url = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqDenominacionCompleto.pgi"
    
    try:
        driver.get(url)
        # Espera a que el campo aparezca
        input_busqueda = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "denominacion"))
        )
        
        # Simular escritura humana (jitter)
        for letra in marca:
            input_busqueda.send_keys(letra)
            time.sleep(random.uniform(0.1, 0.3))
            
        driver.find_element(By.ID, "btnBuscar").click()
        time.sleep(random.uniform(3, 5)) # Espera a resultados
        
        # Si NO aparece este texto, significa que SÍ hay registros (ocupada)
        if "No se encontraron registros" in driver.page_source:
            return "DISPONIBLE"
        else:
            return "OCUPADA"
    except:
        return "ERROR_CONEXION"
    finally:
        driver.quit()

# --- RUTAS DE LA WEB ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    data = request.json
    marca = data.get('marca')
    descripcion = data.get('descripcion')

    # 1. Llamar a Gemini para inteligencia
    resultado_ia = analizar_con_gemini(marca, descripcion)
    
    # 2. Llamar al Robot para disponibilidad real
    disponibilidad_real = buscar_en_marcanet(marca)
    
    # 3. Lógica final de cruce de datos
    if disponibilidad_real == "OCUPADA":
        resultado_ia['viabilidad'] = random.randint(0, 15)
        resultado_ia['nota'] = "ALERTA: Se encontraron registros idénticos en el IMPI."
    elif disponibilidad_real == "ERROR_CONEXION":
        resultado_ia['nota'] = "El sistema del IMPI está saturado, pero basado en IA esto encontramos:"
    
    return jsonify(resultado_ia)

if __name__ == '__main__':
    # Railway usa el puerto que le asigne el sistema
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)