#!/usr/bin/env python3
import sys
import re
from datetime import datetime

backup = f"sistema_uber_unificado_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
print(f"[INFO] Creando backup: {backup}")

with open('sistema_uber_unificado.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open(backup, 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Backup creado")

new_coordinate_class = '''@dataclass
class Coordinate:
    latitude: float
    longitude: float
    altitude: float = 0.0
    accuracy: float = 0.0
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if not (-90.0 <= self.latitude <= 90.0) or abs(self.latitude) > 1000:
            print(f"[WARNING] Latitude invalida: {self.latitude}. Corrigiendo a 0.0")
            self.latitude = 0.0
        if not (-180.0 <= self.longitude <= 180.0) or abs(self.longitude) > 1000:
            print(f"[WARNING] Longitude invalida: {self.longitude}. Corrigiendo a 0.0")
            self.longitude = 0.0
        if abs(self.latitude) < 0.001 and abs(self.longitude) < 0.001:
            print(f"[WARNING] Coordenadas en (0,0). Posible error de sensor.")
        self.latitude = round(self.latitude, 8)
        self.longitude = round(self.longitude, 8)
        if self.accuracy < 0:
            self.accuracy = 0.0
        if self.accuracy > 1000:
            print(f"[WARNING] Accuracy invalida: {self.accuracy}. Limitando a 1000m")
            self.accuracy = 1000.0
        if isinstance(self.timestamp, float):
            self._datetime = datetime.fromtimestamp(self.timestamp, timezone.utc)
        else:
            self._datetime = datetime.now(timezone.utc)
        self.timestamp = self._datetime.timestamp()
    
    def distance_to(self, other: 'Coordinate') -> float:
        lat1 = math.radians(self.latitude)
        lon1 = math.radians(self.longitude)
        lat2 = math.radians(other.latitude)
        lon2 = math.radians(other.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat * 0.5) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon * 0.5) ** 2
        return (EARTH_RADIUS_M / 1000.0) * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    def distance_to_meters(self, other: 'Coordinate') -> float:
        return self.distance_to(other) * 1000.0
    
    def bearing_to(self, other: 'Coordinate') -> float:
        lat1 = math.radians(self.latitude)
        lon1 = math.radians(self.longitude)
        lat2 = math.radians(other.latitude)
        lon2 = math.radians(other.longitude)
        dlon = lon2 - lon1
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        return (math.degrees(math.atan2(x, y)) + 360) % 360'''

pattern = r'@dataclass\nclass Coordinate:.*?(?=\n(?:@dataclass|class |def ))'
match = re.search(pattern, content, re.DOTALL)

if match:
    print("[INFO] Reemplazando clase Coordinate...")
    new_content = content[:match.start()] + new_coordinate_class + '\n\n' + content[match.end():]
    with open('sistema_uber_unificado.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("[OK] Clase Coordinate actualizada")
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
else:
    print("[ERROR] No se encontro la clase Coordinate")
    sys.exit(1)
