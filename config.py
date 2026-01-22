import os

class Config:
    SECRET_KEY = "tu_clave_secreta_aqui"
    
    # Credenciales de Supabase
    SUPABASE_URL = "https://clpypbkkjwaixbexdepd.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNscHlwYmtrandhaXhiZXhkZXBkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQxNzk0MjMsImV4cCI6MjA3OTc1NTQyM30.-RgEv47KXtPqFjeL1UI5Ocmj0HOzHCGaxl3SJGF-8fE"
    
    ADMIN_EMAILS = ("admin@gmail.com")
    LIMITE_EMPLEADO = 5000000
    LIMITE_INDEPENDIENTE = 1500000
    TASA_INTERES_MENSUAL = 0.025