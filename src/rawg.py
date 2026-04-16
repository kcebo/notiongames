import requests
import re
from config import RAWG_API_KEY

BASE_URL = "https://api.rawg.io/api"

def _get(endpoint, params=None):
    params = params or {}
    params["key"] = RAWG_API_KEY
    res = requests.get(f"{BASE_URL}/{endpoint}", params=params)
    return res.json() if res.status_code == 200 else None

def search_game(title):
    # CAMBIO: Subimos page_size a 10 y devolvemos la lista entera de results
    data = _get("games", {"search": title, "page_size": 10})
    if data and "results" in data:
        return data["results"]  # Devolvemos la lista completa
    return []

def get_game_details(game_id):
    return _get(f"games/{game_id}")

def get_game_series(game_id):
    """Busca la serie/saga específica de un juego"""
    return _get(f"games/{game_id}/game-series")

def get_developer_details(dev_id):
    """Obtiene los detalles de una desarrolladora, incluyendo su sitio web"""
    url = f"https://api.rawg.io/api/developers/{dev_id}?key={RAWG_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def get_wikipedia_images_list(company_name):
    """Busca específicamente logos vectoriales (SVG) y los devuelve como PNG de 1000px"""
    headers = {'User-Agent': 'NotionflixBot/1.2 (contacto@ejemplo.com)'}
    images = []
    try:
        wikimedia_api = "https://commons.wikimedia.org/w/api.php"
        # Limpiamos el nombre (ej: Activision Publishing -> Activision)
        clean_name = re.sub(r'(\s*,\s*|,\s*|\s*|,)(Inc\.|Ltd\.|Publishing|LLC)$', '', company_name, flags=re.IGNORECASE).strip()
        
        # Buscamos archivos que contengan el nombre y sean .svg
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": f"file:{clean_name} .svg",
            "srnamespace": 6,
            "format": "json",
            "srlimit": 20, 
            "origin": "*"
        }
        
        resp = requests.get(wikimedia_api, params=search_params, headers=headers)
        if resp.status_code == 200:
            results = resp.json().get("query", {}).get("search", [])
            for res in results:
                title = res['title']
                
                # Pedimos la URL de renderizado (PNG) para el SVG
                info_params = {
                    "action": "query",
                    "prop": "imageinfo",
                    "titles": title,
                    "iiprop": "url",
                    "iiurlwidth": 1000, 
                    "format": "json",
                    "origin": "*"
                }
                info_resp = requests.get(wikimedia_api, params=info_params, headers=headers)
                if info_resp.status_code == 200:
                    pages = info_resp.json().get("query", {}).get("pages", {})
                    for pid in pages:
                        if "imageinfo" in pages[pid]:
                            info = pages[pid]["imageinfo"][0]
                            # Usamos thumburl porque es el PNG generado a partir del SVG
                            img_url = info.get("thumburl")
                            if img_url:
                                images.append(img_url)
        
        return list(dict.fromkeys(images))
    except Exception as e:
        print(f"⚠️ Error buscando SVG: {e}")
        return []