import re
from notion import get_pages, get_dynamic_properties, update_page, create_page, _request
from rawg import search_game, get_game_details, get_game_series, get_developer_details, get_wikipedia_images_list
from config import VIDEOGAME_DB_ID, COLLECTION_DB_ID

def clean_html(raw_html):
    if not raw_html: return ""
    return re.sub('<.*?>', '', raw_html).strip()

def select_game_interactive(query):
    results = search_game(query)
    if not results: return None
    games = results[:10] 

    print(f"\n🔍 Resultados para '{query}':")
    for i, g in enumerate(games):
        year = f"({g.get('released').split('-')[0]})" if g.get('released') else "N/A"
        print(f"{i+1}. {g['name']} {year}")
    
    user_input = input(f"\nElegí (1-{len(games)}), [Enter] para el primero, o '0' para saltar: ").strip()
    if user_input == "": return games[0]
    try:
        choice = int(user_input)
        if choice == 0: return None
        return games[choice-1] if 1 <= choice <= len(games) else None
    except: return None

def get_or_create_company(company_name, company_id_rawg, col_map_comp, stats):
    nombre_col_comp = col_map_comp.get("titulo")
    if not nombre_col_comp: return None

    # Buscamos si ya existe
    query = {"filter": {"property": nombre_col_comp, "title": {"equals": company_name}}}
    results = _request("post", f"databases/{COLLECTION_DB_ID}/query", json=query)
    
    if results and results.get("results"):
        return results["results"][0]["id"]
    
    # --- Lógica de Empresa Nueva con Selección de Poster/Logo ---
    print(f"\n🏢 Nueva empresa detectada: {company_name}")
    img_list = get_wikipedia_images_list(company_name)
    selected_img = None

    if img_list:
        print(f"🖼️  Elegí un logo (SVG -> PNG) para {company_name}:")
        for i, url in enumerate(img_list):
            print(f"{i+1}. {url.split('/')[-1]}")
        
        choice = input(f"Elegí (1-{len(img_list)}), [Enter] para el primero, o 's' para RAWG: ").strip()
        if choice == "": selected_img = img_list[0]
        elif choice.isdigit() and 0 < int(choice) <= len(img_list):
            selected_img = img_list[int(choice)-1]
    
    if not selected_img:
        dev_details = get_developer_details(company_id_rawg)
        selected_img = dev_details.get("image_background") if dev_details else None

    props = {nombre_col_comp: {"title": [{"text": {"content": company_name}}]}}
    
    # Agregamos el poster si la columna existe y tenemos imagen
    if "poster" in col_map_comp and selected_img:
        props[col_map_comp["poster"]] = {
            "files": [{"name": "Logo", "type": "external", "external": {"url": selected_img}}]
        }
        
    res = create_page(COLLECTION_DB_ID, props)
    if res:
        stats['detalles_compania'].append(company_name)
        return res["id"]
    return None

def process_game_data(full_game, prop_map, prop_map_comp, stats, page_id=None):
    col_titulo = prop_map.get("titulo")
    if not col_titulo: return
    
    props = {col_titulo: {"title": [{"text": {"content": full_game.get("name")}}]}}
    
    if full_game.get("developers"):
        main_dev = full_game["developers"][0]
        comp_id = get_or_create_company(main_dev["name"], main_dev["id"], prop_map_comp, stats)
        if comp_id and "saga" in prop_map:
            props[prop_map["saga"]] = {"relation": [{"id": comp_id}]}

    if "año" in prop_map and full_game.get("released"):
        props[prop_map["año"]] = {"number": int(full_game["released"].split("-")[0])}

    if "descripcion" in prop_map:
        desc = (full_game.get("description_raw") or clean_html(full_game.get("description")))[:2000]
        props[prop_map["descripcion"]] = {"rich_text": [{"text": {"content": desc}}]}

    if "generos" in prop_map and full_game.get("genres"):
        props[prop_map["generos"]] = {"multi_select": [{"name": g['name']} for g in full_game['genres']]}

    if "plataforma" in prop_map and full_game.get("platforms"):
        props[prop_map["plataforma"]] = {"multi_select": [{"name": p['platform']['name']} for p in full_game['platforms']]}

    if "poster" in prop_map and full_game.get("background_image"):
        props[prop_map["poster"]] = {
            "files": [{"name": "Poster", "type": "external", "external": {"url": full_game["background_image"]}}]
        }

    if page_id:
        update_page(page_id, props)
        stats['detalles_actualizados'].append(full_game['name'])
    else:
        # Evitar duplicados en creación automática
        query = {"filter": {"property": col_titulo, "title": {"equals": full_game.get("name")}}}
        exists = _request("post", f"databases/{VIDEOGAME_DB_ID}/query", json=query)
        if not exists or not exists.get("results"):
            create_page(VIDEOGAME_DB_ID, props)
            stats['detalles_creados'].append(full_game['name'])

def main():
    print("🚀 Iniciando NotionGames Sync (Modo Silencioso)...")
    stats = {
        'detalles_creados': [], 'detalles_actualizados': [],
        'detalles_compania': [], 'detalles_omitidos': []
    }
    
    prop_map_games = get_dynamic_properties(VIDEOGAME_DB_ID)
    prop_map_comp = get_dynamic_properties(COLLECTION_DB_ID)
    procesados = set()
    pages = get_pages(VIDEOGAME_DB_ID)
    
    for page in pages:
        col_t = prop_map_games.get("titulo")
        col_p = prop_map_games.get("poster")
        if not col_t or not page["properties"][col_t]["title"]: continue
        
        current_title = page["properties"][col_t]["title"][0]["text"]["content"]
        if current_title in procesados: continue

        # Filtro de póster: Solo procesar si está vacío
        if col_p and page["properties"].get(col_p, {}).get("files"):
            if len(page["properties"][col_p]["files"]) > 0:
                stats['detalles_omitidos'].append(current_title)
                continue

        selected = select_game_interactive(current_title)
        if selected:
            full = get_game_details(selected['id'])
            process_game_data(full, prop_map_games, prop_map_comp, stats, page["id"])
            procesados.add(full['name'])

            if full.get("game_series_count", 0) > 0:
                series_data = get_game_series(selected['id'])
                if series_data and series_data.get("results"):
                    for rel_game in series_data["results"]:
                        if rel_game['name'] not in procesados:
                            full_rel = get_game_details(rel_game['id'])
                            process_game_data(full_rel, prop_map_games, prop_map_comp, stats)
                            procesados.add(rel_game['name'])

    # --- RESUMEN FINAL ---
    print("\n" + "="*35)
    print("📊 RESUMEN DE ACTIVIDAD")
    print("="*35)
    print(f"✨ Creados:     {len(stats['detalles_creados'])}")
    print(f"✅ Actualizados: {len(stats['detalles_actualizados'])}")
    print(f"🏢 Compañías:   {len(stats['detalles_compania'])}")
    print(f"⏩ Omitidos:    {len(stats['detalles_omitidos'])}")
    print("="*35)

    if input("\n¿Desea ver el detalle de los cambios? (s/n): ").lower() == 's':
        # Ordenamos alfabéticamente antes de mostrar
        for label, key in [("✨ CREADOS", 'detalles_creados'), 
                           ("✅ ACTUALIZADOS", 'detalles_actualizados'), 
                           ("🏢 COMPAÑÍAS", 'detalles_compania')]:
            if stats[key]:
                print(f"\n{label}:")
                for item in sorted(stats[key]): # <--- Aquí se aplica el orden
                    print(f" - {item}")
    
    if input("\n¿Desea ver los juegos omitidos (con póster)? (s/n): ").lower() == 's':
        if stats['detalles_omitidos']:
            print("\n⏩ OMITIDOS:")
            for o in sorted(stats['detalles_omitidos']): # <--- Orden alfabético
                print(f" - {o}")

    print("\n🏁 Proceso finalizado.")
    
if __name__ == "__main__":
    main()