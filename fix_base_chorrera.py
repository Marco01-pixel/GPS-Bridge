#!/usr/bin/env python3
import re
from datetime import datetime

backup = f"sistema_uber_unificado_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
print(f"[INFO] Creando backup: {backup}")

with open('sistema_uber_unificado.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open(backup, 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Backup creado")

# 1. Agregar constante BASE_LOCATION después de EARTH_RADIUS_M
if 'BASE_LOCATION' not in content:
    pattern_earth = r'(EARTH_RADIUS_M\s*=\s*[\d_\.]+)'
    match_earth = re.search(pattern_earth, content)
    if match_earth:
        base_const = '''

# Coordenadas base de respaldo: La Chorrera, Panama
BASE_LOCATION_LAT = 8.875
BASE_LOCATION_LON = -79.78
BASE_LOCATION_NAME = "La Chorrera, Panama"'''
        content = content[:match_earth.end()] + base_const + content[match_earth.end():]
        print("[OK] Constante BASE_LOCATION agregada")
    else:
        print("[WARN] No se encontro EARTH_RADIUS_M, usando valores hardcoded")

# 2. Reemplazar __post_init__ para usar La Chorrera como fallback
old_post_init = r'''    def __post_init__\(self\):
        self\._valid = True
        if not \(-90\.0 <= self\.latitude <= 90\.0\) or abs\(self\.latitude\) > 1000:
            print\(f"\[WARNING\] Latitude invalida detectada: \{self\.latitude\}\. Marcando como invalida"\)
            self\._valid = False
        if not \(-180\.0 <= self\.longitude <= 180\.0\) or abs\(self\.longitude\) > 1000:
            print\(f"\[WARNING\] Longitude invalida detectada: \{self\.longitude\}\. Marcando como invalida"\)
            self\._valid = False
        if abs\(self\.latitude\) < 0\.001 and abs\(self\.longitude\) < 0\.001:
            print\(f"\[WARNING\] Coordenadas en \(0,0\)\. Posible error de sensor\."\)
            self\._valid = False
        self\.latitude = round\(self\.latitude, 8\)
        self\.longitude = round\(self\.longitude, 8\)
        if self\.accuracy < 0:
            self\.accuracy = 0\.0
        if self\.accuracy > 1000:
            self\.accuracy = 1000\.0
        if isinstance\(self\.timestamp, float\):
            self\._datetime = datetime\.fromtimestamp\(self\.timestamp, timezone\.utc\)
        else:
            self\._datetime = datetime\.now\(timezone\.utc\)
        self\.timestamp = self\._datetime\.timestamp\(\)'''

new_post_init = '''    def __post_init__(self):
        self._valid = True
        self._is_fallback = False
        self._original_source = self.source
        
        # Detectar coordenadas invalidas
        lat_invalid = not (-90.0 <= self.latitude <= 90.0) or abs(self.latitude) > 1000
        lon_invalid = not (-180.0 <= self.longitude <= 180.0) or abs(self.longitude) > 1000
        zero_zero = abs(self.latitude) < 0.001 and abs(self.longitude) < 0.001
        
        if lat_invalid or lon_invalid or zero_zero:
            if lat_invalid:
                print(f"[WARNING] Latitude invalida: {self.latitude}. Usando base La Chorrera")
            if lon_invalid:
                print(f"[WARNING] Longitude invalida: {self.longitude}. Usando base La Chorrera")
            if zero_zero:
                print(f"[WARNING] Coordenadas (0,0). Usando base La Chorrera, Panama")
            
            # Reemplazar con coordenadas base de La Chorrera, Panama
            try:
                self.latitude = BASE_LOCATION_LAT
                self.longitude = BASE_LOCATION_LON
            except NameError:
                self.latitude = 8.875
                self.longitude = -79.78
            
            self.source = f"{self.source}_fallback"
            self._is_fallback = True
            self.accuracy = max(self.accuracy, 500.0)
        
        # Limitar precision a 8 decimales
        self.latitude = round(self.latitude, 8)
        self.longitude = round(self.longitude, 8)
        
        # Validar accuracy
        if self.accuracy < 0:
            self.accuracy = 0.0
        if self.accuracy > 5000:
            self.accuracy = 5000.0
        
        # Timestamp
        if isinstance(self.timestamp, float):
            self._datetime = datetime.fromtimestamp(self.timestamp, timezone.utc)
        else:
            self._datetime = datetime.now(timezone.utc)
        self.timestamp = self._datetime.timestamp()'''

content = re.sub(old_post_init, new_post_init, content, flags=re.DOTALL)

# 3. Actualizar is_valid para considerar fallback como valido
old_is_valid = r'''    def is_valid\(self\) -> bool:
        """Verifica si las coordenadas son fisicamente posibles\."""
        return getattr\(self, '_valid', True\)'''

new_is_valid = '''    def is_valid(self) -> bool:
        """Verifica si las coordenadas son fisicamente posibles."""
        return getattr(self, '_valid', True)
    
    def is_fallback(self) -> bool:
        """Indica si esta coordenada es un fallback (no lectura real del sensor)."""
        return getattr(self, '_is_fallback', False)'''

content = re.sub(old_is_valid, new_is_valid, content, flags=re.DOTALL)

with open('sistema_uber_unificado.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Sistema configurado con base La Chorrera, Panama")

import subprocess
result = subprocess.run(['python3', '-m', 'py_compile', 'sistema_uber_unificado.py'], 
                      capture_output=True, text=True)

if result.returncode == 0:
    print("[OK] Sintaxis valida")
    print(f"\n[INFO] Backup guardado: {backup}")
    print("\n[+] Cambios aplicados:")
    print("  - Coordenadas invalidas -> reemplazadas por La Chorrera (8.875, -79.78)")
    print("  - Fallback marcado con flag _is_fallback")
    print("  - Source modificado a 'xxx_fallback' para debugging")
    print("  - Accuracy minima de 500m para fallbacks")
else:
    print("[ERROR] Errores de sintaxis:")
    print(result.stderr)
    with open(backup, 'r') as f:
        original = f.read()
    with open('sistema_uber_unificado.py', 'w') as f:
        f.write(original)
    print("[OK] Backup restaurado")
