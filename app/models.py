from supabase import create_client, Client
from config import Config

# Inicializar cliente único
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# --- FUNCIONES GENÉRICAS ---

def cargar_datos(tabla):
    """Trae todos los registros de una tabla"""
    # .data devuelve la lista de diccionarios
    response = supabase.table(tabla).select("*").execute()
    return response.data

def guardar_registro(tabla, datos):
    """Crea un nuevo registro en la base de datos"""
    # Eliminamos 'id' si existe para que la base de datos lo genere automáticamente
    if 'id' in datos: 
        del datos['id']
    
    response = supabase.table(tabla).insert(datos).execute()
    return response.data

def actualizar_registro(tabla, id_registro, datos_nuevos):
    """Actualiza un registro existente"""
    response = supabase.table(tabla).update(datos_nuevos).eq("id", id_registro).execute()
    return response.data

# --- FUNCIONES ESPECÍFICAS (Helpers) ---

def cargar_perfil(correo):
    # Busca usuario por correo
    response = supabase.table("usuarios").select("*").eq("correo", correo).execute()
    # Retorna el primer resultado o None
    return response.data[0] if response.data else None