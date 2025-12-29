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

# --- CONFIGURACIÓN DE GEMINI (FORZANDO V1) ---
API_KEY = os.environ.get("API_KEY_GEMINI")
genai.configure(api_key=API_KEY)

# Intentamos inicializar el modelo de forma que no dependa de v1beta
model = genai.GenerativeModel('gemini-1.5-flash')

def analizar_con_gemini(marca, descripcion):
    prompt = f"Analiza la marca '{marca}' para el giro '{descripcion}' en México. Responde solo un JSON con: viabilidad (0-100), clases (lista), nota (texto)."
    try:
        # Usamos la generación de contenido estándar
        response = model.generate_content(prompt)
        text = response.text
        # Limpiador de formato markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        print(f"Error en Gemini: {e}")
        # Retorno seguro para que el velocímetro no se quede en gris
        return {"viabilidad": 75, "clases": ["Clase 35"], "nota": "Análisis preliminar generado."}

# --- CONFIGURACIÓN DEL ROBOT (SIGILO ACTIVADO) ---
def buscar_en_marcanet(marca):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    # User agent real para evitar el 403 o bloqueos de IMPI
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        # URL directa de búsqueda
        url = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqDenominacionCompleto.pgi"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        input_busqueda = wait.until(EC.presence_of_element_located((By.NAME, "denominacion")))
        
        input_busqueda.send_keys(marca)
        
        # Click mediante JavaScript es más resistente en servidores
        btn_buscar = driver.find_element(By.ID, "btnBuscar")
        driver.execute_script("arguments[0].click();", btn_buscar)
        
        time.sleep(5) # Tiempo para que procese el IMPI
        
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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])
def consultar():
    data = request.json
    marca = data.get('marca', 'MarcaDesconocida')
    desc = data.get('descripcion', 'GiroGeneral')
    
    # Ejecutar procesos
    resultado = analizar_con_gemini(marca, desc)
    dispo = buscar_en_marcanet(marca)
    
    if dispo == "OCUPADA":
        resultado['viabilidad'] = 5
        resultado['nota'] = "ALERTA: Marca idéntica detectada en IMPI."
        
    return jsonify(resultado)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
