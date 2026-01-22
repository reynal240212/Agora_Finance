from werkzeug.security import generate_password_hash

def crear_hash():
    password = input("Escribe la contraseña que quieres encriptar: ")
    # Generamos el hash usando el método scrypt (estándar de Flask)
    hash_generado = generate_password_hash(password)
    
    print("\n--- NUEVO HASH GENERADO ---")
    print(hash_generado)
    print("---------------------------\n")
    

if __name__ == "__main__":
    crear_hash()