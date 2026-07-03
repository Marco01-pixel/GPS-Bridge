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

pattern = r"(    def bearing_to\(self, other: 'Coordinate'\) -> float:.*?return \(math\.degrees\(math\.atan2\(x, y\)\) \+ 360\) % 360)"
match = re.search(pattern, content, re.DOTALL)

if match:
    print("[INFO] Agregando metodo is_valid()...")
    is_valid_method = '''
    
    def is_valid(self) -> bool:
        """Verifica si las coordenadas son fisicamente posibles."""
        if not (-90.0 <= self.latitude <= 90.0):
            return False
        if not (-180.0 <= self.longitude <= 180.0):
            return False
        if abs(self.latitude) < 0.001 and abs(self.longitude) < 0.001:
            return False
        return True'''
    
    new_content = content[:match.end()] + is_valid_method + content[match.end():]
    
    with open('sistema_uber_unificado.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("[OK] Metodo is_valid() agregado")
    
    import subprocess
    result = subprocess.run(['python3', '-m', 'py_compile', 'sistema_uber_unificado.py'], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print("[OK] Sintaxis valida")
        print(f"\n[INFO] Backup guardado: {backup}")
        print("[INFO] Ahora puedes ejecutar el sistema normalmente")
    else:
        print("[ERROR] Errores de sintaxis:")
        print(result.stderr)
        with open(backup, 'r') as f:
            original = f.read()
        with open('sistema_uber_unificado.py', 'w') as f:
            f.write(original)
        print("[OK] Backup restaurado")
else:
    print("[ERROR] No se encontro el metodo bearing_to")
    import sys
    sys.exit(1)
