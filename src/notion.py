import requests
from config import NOTION_TOKEN

BASE_URL = "https://api.notion.com/v1/"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def _request(method, endpoint, json=None):
    url = f"{BASE_URL}{endpoint}"
    res = requests.request(method, url, headers=HEADERS, json=json)
    return res.json() if res.status_code == 200 else None

def get_dynamic_properties(db_id):
    """Mapea las columnas de Notion por su tipo"""
    data = _request("get", f"databases/{db_id}")
    if not data: return {}
    
    schema = data.get("properties", {})
    prop_map = {}
    
    for name, details in schema.items():
        t = details.get("type")
        # Guardamos el nombre real de la columna según su tipo
        if t == "title": prop_map["titulo"] = name
        elif t == "files": prop_map["poster"] = name
        elif t == "relation": prop_map["saga"] = name
        elif t == "number": prop_map["año"] = name
        elif t == "multi_select":
            # Si hay dos multi-select, tratamos de diferenciar por nombre
            if "plat" in name.lower(): prop_map["plataforma"] = name
            else: prop_map["generos"] = name
        elif t == "rich_text": prop_map["descripcion"] = name
            
    return prop_map

def get_pages(db_id):
    """Obtiene TODAS las páginas de la base de datos manejando la paginación."""
    results = []
    payload = {"page_size": 100}  # Máximo permitido por Notion
    
    while True:
        data = _request("post", f"databases/{db_id}/query", json=payload)
        if not data:
            break
            
        results.extend(data.get("results", []))
        
        # Si hay más de 100, Notion nos da un cursor para la siguiente tanda
        if data.get("has_more"):
            payload["start_cursor"] = data.get("next_cursor")
        else:
            break
            
    return results

def update_page(page_id, properties):
    return _request("patch", f"pages/{page_id}", json={"properties": properties})

def create_page(db_id, properties):
    payload = {"parent": {"database_id": db_id}, "properties": properties}
    return _request("post", "pages", json=payload)