import os
import time
import json
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURACIÓN DE GEMINI ---
API_KEY = os.environ.get("API_KEY_GEMINI")
genai.configure(api_key=API_KEY)

# Inicialización simplificada para evitar errores de versión 404
model = genai.GenerativeModel('gemini-1.5-flash')

def analizar_con_gemini(marca, descripcion):
    prompt = f"Analiza la marca '{marca}' para el giro '{descripcion}' en México. Responde únicamente en formato JSON con estas llaves: viabilidad (número 0-100), clases (lista de textos), nota (texto breve)."
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.strip()
        # Limpieza de markdown en caso de que Gemini lo incluya
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0]
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0]
        
        return json.loads(clean_text)
    except Exception as e:
        print(f"Error en Gemini: {e}")
        return {"viabilidad": 50, "clases": ["Clase 35: Servicios comerciales"], "nota": "IA en mantenimiento, análisis básico disponible."}

# --- CONFIGURACIÓN DEL ROBOT ---
def buscar_en_marcanet(marca):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # User-Agent para simular un navegador real
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        url = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqDenominacionCompleto.pgi"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        input_busqueda = wait.until(EC.presence_of_element_located((By.NAME, "denominacion")))
        
        # Simulación de escritura
        input_busqueda.send_keys(marca)
        
        btn_buscar = driver.find_element(By.ID, "btnBuscar")
        # Usamos JavaScript para el clic, es más efectivo en modo invisible
        driver.execute_script("arguments[0].click();", btn_buscar)
        
        # Tiempo de espera para que el IMPI procese
        time.sleep(5)
        
        if "No se encontraron registros" in driver.page_source:
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
    marca = data.get('marca', '')
    desc = data.get('descripcion', '')
    
    # Ejecutar ambos procesos
    resultado = analizar_con_gemini(marca, desc)
    dispo = buscar_en_marcanet(marca)
    
    if dispo == "OCUPADA":
        resultado['viabilidad'] = 10
        resultado['nota'] = "¡RIESGO ALTO! Se detectaron marcas idénticas en el IMPI."
    
    return jsonify(resultado)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
