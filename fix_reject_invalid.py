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

old_post_init = r'''    def __post_init__\(self\):
        if not \(-90\.0 <= self\.latitude <= 90\.0\) or abs\(self\.latitude\) > 1000:
            print\(f"\[WARNING\] Latitude invalida: \{self\.latitude\}\. Corrigiendo a 0\.0"\)
            self\.latitude = 0\.0
        if not \(-180\.0 <= self\.longitude <= 180\.0\) or abs\(self\.longitude\) > 1000:
            print\(f"\[WARNING\] Longitude invalida: \{self\.longitude\}\. Corrigiendo a 0\.0"\)
            self\.longitude = 0\.0
        if abs\(self\.latitude\) < 0\.001 and abs\(self\.longitude\) < 0\.001:
            print\(f"\[WARNING\] Coordenadas en \(0,0\)\. Posible error de sensor\."\)
        self\.latitude = round\(self\.latitude, 8\)
        self\.longitude = round\(self\.longitude, 8\)
        if self\.accuracy < 0:
            self\.accuracy = 0\.0
        if self\.accuracy > 1000:
            print\(f"\[WARNING\] Accuracy invalida: \{self\.accuracy\}\. Limitando a 1000m"\)
            self\.accuracy = 1000\.0
        if isinstance\(self\.timestamp, float\):
            self\._datetime = datetime\.fromtimestamp\(self\.timestamp, timezone\.utc\)
        else:
            self\._datetime = datetime\.now\(timezone\.utc\)
        self\.timestamp = self\._datetime\.timestamp\(\)'''

new_post_init = '''    def __post_init__(self):
        self._valid = True
        if not (-90.0 <= self.latitude <= 90.0) or abs(self.latitude) > 1000:
            print(f"[WARNING] Latitude invalida detectada: {self.latitude}. Marcando como invalida")
            self._valid = False
        if not (-180.0 <= self.longitude <= 180.0) or abs(self.longitude) > 1000:
            print(f"[WARNING] Longitude invalida detectada: {self.longitude}. Marcando como invalida")
            self._valid = False
        if abs(self.latitude) < 0.001 and abs(self.longitude) < 0.001:
            print(f"[WARNING] Coordenadas en (0,0). Posible error de sensor.")
            self._valid = False
        self.latitude = round(self.latitude, 8)
        self.longitude = round(self.longitude, 8)
        if self.accuracy < 0:
            self.accuracy = 0.0
        if self.accuracy > 1000:
            self.accuracy = 1000.0
        if isinstance(self.timestamp, float):
            self._datetime = datetime.fromtimestamp(self.timestamp, timezone.utc)
        else:
            self._datetime = datetime.now(timezone.utc)
        self.timestamp = self._datetime.timestamp()'''

content = re.sub(old_post_init, new_post_init, content, flags=re.DOTALL)

old_is_valid = r'''    def is_valid\(self\) -> bool:
        """Verifica si las coordenadas son fisicamente posibles\."""
        if not \(-90\.0 <= self\.latitude <= 90\.0\):
            return False
        if not \(-180\.0 <= self\.longitude <= 180\.0\):
            return False
        if abs\(self\.latitude\) < 0\.001 and abs\(self\.longitude\) < 0\.001:
            return False
        return True'''

new_is_valid = '''    def is_valid(self) -> bool:
        """Verifica si las coordenadas son fisicamente posibles."""
        return getattr(self, '_valid', True)'''

content = re.sub(old_is_valid, new_is_valid, content, flags=re.DOTALL)

with open('sistema_uber_unificado.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Clase Coordinate actualizada para rechazar lecturas invalidas")

import subprocess
result = subprocess.run(['python3', '-m', 'py_compile', 'sistema_uber_unificado.py'], 
                      capture_output=True, text=True)

if result.returncode == 0:
    print("[OK] Sintaxis valida")
    print(f"\n[INFO] Backup guardado: {backup}")
else:
    print("[ERROR] Errores de sintaxis:")
    print(result.stderr)
    with open(backup, 'r') as f:
        original = f.read()
    with open('sistema_uber_unificado.py', 'w') as f:
        f.write(original)
    print("[OK] Backup restaurado")
