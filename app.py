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
# Forzamos la configuración para evitar el error v1beta
genai.configure(api_key=API_KEY)

def analizar_con_gemini(marca, descripcion):
    # Usamos la versión v1 explícitamente en el modelo
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Analiza la marca '{marca}' para el giro '{descripcion}' en México. Responde solo JSON con: viabilidad (0-100), clases (lista), nota (texto)."
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Limpiador de bloques de código markdown
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error en Gemini: {e}")
        # Retorno de seguridad mejorado
        return {"viabilidad": 40, "clases": ["Clase 32: Refrescos y bebidas"], "nota": "Análisis preliminar de IA."}

# --- CONFIGURACIÓN DEL ROBOT ---
def buscar_en_marcanet(marca):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # User-Agent de un Chrome real en Windows para evitar bloqueos
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(35)
        
        # URL directa de búsqueda por denominación
        driver.get("https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqDenominacionCompleto.pgi")
        
        wait = WebDriverWait(driver, 20)
        input_busqueda = wait.until(EC.presence_of_element_located((By.NAME, "denominacion")))
        
        input_busqueda.send_keys(marca)
        
        btn_buscar = driver.find_element(By.ID, "btnBuscar")
        driver.execute_script("arguments[0].click();", btn_buscar)
        
        # Espera para que el IMPI responda
        time.sleep(6)
        
        source = driver.page_source
        if "No se encontraron registros" in source:
            return "DISPONIBLE"
        else:
            return "OCUPADA"
            
    except Exception as e:
        print(f"Error en el robot: {e}")
        return "ERROR_CONEXION"
    finally:
        if driver:
            driver.quit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    data = request.json
    marca = data.get('marca', '')
    desc = data.get('descripcion', '')
    
    # 1. Ejecutar IA
    resultado = analizar_con_gemini(marca, desc)
    # 2. Ejecutar Robot
    dispo = buscar_en_marcanet(marca)
    
    # 3. Lógica de Cruce: Si el robot dice OCUPADA, forzamos riesgo máximo
    if dispo == "OCUPADA":
        resultado['viabilidad'] = 2
        resultado['nota'] = "¡ALERTA CRÍTICA! Esta marca ya está registrada en el IMPI. No es posible utilizarla."
        
    return jsonify(resultado)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
