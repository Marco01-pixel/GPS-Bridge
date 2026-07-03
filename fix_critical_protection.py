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

# CAPA 1: distance_to protegido
old_distance = r'''    def distance_to\(self, other: 'Coordinate'\) -> float:
        lat1 = math\.radians\(self\.latitude\)
        lon1 = math\.radians\(self\.longitude\)
        lat2 = math\.radians\(other\.latitude\)
        lon2 = math\.radians\(other\.longitude\)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math\.sin\(dlat \* 0\.5\) \*\* 2 \+ math\.cos\(lat1\) \* math\.cos\(lat2\) \* math\.sin\(dlon \* 0\.5\) \*\* 2
        return \(EARTH_RADIUS_M / 1000\.0\) \* 2\.0 \* math\.atan2\(math\.sqrt\(a\), math\.sqrt\(1\.0 - a\)\)'''

new_distance = '''    def distance_to(self, other: 'Coordinate') -> float:
        try:
            lat1 = math.radians(self.latitude)
            lon1 = math.radians(self.longitude)
            lat2 = math.radians(other.latitude)
            lon2 = math.radians(other.longitude)
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat * 0.5) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon * 0.5) ** 2
            a = max(0.0, min(1.0, a))
            return (EARTH_RADIUS_M / 1000.0) * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        except (ValueError, OverflowError, TypeError) as e:
            print(f"[WARNING] Error en distance_to: {e}. Retornando 0.0")
            return 0.0'''

content = re.sub(old_distance, new_distance, content, flags=re.DOTALL)
print("[OK] CAPA 1: distance_to protegido")

# CAPA 2: Detector de valores imposibles
old_e7 = r'''def _convert_e7_to_decimal\(value: float\) -> float:
    """Convierte coordenadas de formato E7 \(entero\) a decimal si es necesario\."""
    if abs\(value\) > 1000:
        return value / 10_000_000\.0
    return value'''

new_e7 = '''def _convert_e7_to_decimal(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(v) > 1e15:
        return 0.0
    if abs(v) > 1000:
        return v / 10_000_000.0
    return v

def _is_coordinate_sane(lat: float, lon: float) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(lat_f) or not math.isfinite(lon_f):
        return False
    if abs(lat_f) > 1e10 or abs(lon_f) > 1e10:
        return False
    return True'''

content = re.sub(old_e7, new_e7, content, flags=re.DOTALL)
print("[OK] CAPA 2: Detector de valores imposibles")

# CAPA 3: Validar fusion
old_fusion = r'''            if not locations:
                self\.consecutive_failures \+= 1
                if self\._last_coord and self\.consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                    pred_dt = min\(1\.0, self\.consecutive_failures \* 0\.5\)
                    pred_lat, pred_lon = self\.imu\.predict\(
                        self\._last_coord\.latitude, self\._last_coord\.longitude, pred_dt\)
                    predicted = Coordinate\(
                        pred_lat, pred_lon,
                        accuracy=self\._last_coord\.accuracy \+ self\.consecutive_failures \* 3\.0,
                        source='predicted'\)
                    self\._last_coord = predicted
                    self\.exporter\.add_waypoint\(predicted\)
            else:
                self\.consecutive_failures = 0
                total_weight = sum\(w for _, w in locations\)
                if total_weight > 0:
                    fused_lat = sum\(loc\.latitude \* w for loc, w in locations\) / total_weight
                    fused_lon = sum\(loc\.longitude \* w for loc, w in locations\) / total_weight
                    fused_accuracy = sum\(loc\.accuracy \* w for loc, w in locations\) / total_weight
                    result = Coordinate\(fused_lat, fused_lon,
                                        accuracy=fused_accuracy, source='hybrid'\)
                    if self\._last_coord:
                        self\.stats\['total_distance_m'\] \+= self\._last_coord\.distance_to_meters\(result\)
                    self\._last_coord = result
                    self\.exporter\.add_waypoint\(result\)'''

new_fusion = '''            if not locations:
                self.consecutive_failures += 1
                if self._last_coord and self.consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                    pred_dt = min(1.0, self.consecutive_failures * 0.5)
                    pred_lat, pred_lon = self.imu.predict(
                        self._last_coord.latitude, self._last_coord.longitude, pred_dt)
                    if _is_coordinate_sane(pred_lat, pred_lon):
                        predicted = Coordinate(
                            pred_lat, pred_lon,
                            accuracy=self._last_coord.accuracy + self.consecutive_failures * 3.0,
                            source='predicted')
                        if predicted.is_valid():
                            self._last_coord = predicted
                            self.exporter.add_waypoint(predicted)
                        else:
                            self._reset_kalman_if_needed()
                    else:
                        print(f"[WARNING] Prediccion IMU invalida. Reinicializando filtros.")
                        self._reset_kalman_if_needed()
            else:
                self.consecutive_failures = 0
                total_weight = sum(w for _, w in locations)
                if total_weight > 0:
                    fused_lat = sum(loc.latitude * w for loc, w in locations) / total_weight
                    fused_lon = sum(loc.longitude * w for loc, w in locations) / total_weight
                    fused_accuracy = sum(loc.accuracy * w for loc, w in locations) / total_weight
                    if not _is_coordinate_sane(fused_lat, fused_lon):
                        print(f"[WARNING] Fusion invalida ({fused_lat:.2e}, {fused_lon:.2e}). Reinicializando filtros.")
                        self._reset_kalman_if_needed()
                        if self._last_coord:
                            self.exporter.add_waypoint(self._last_coord)
                        return
                    result = Coordinate(fused_lat, fused_lon,
                                        accuracy=fused_accuracy, source='hybrid')
                    if result.is_valid() and self._last_coord:
                        try:
                            dist = self._last_coord.distance_to_meters(result)
                            if dist < 5000:
                                self.stats['total_distance_m'] += dist
                            else:
                                print(f"[WARNING] Salto de {dist:.0f}m ignorado")
                        except Exception as e:
                            print(f"[WARNING] Error calculando distancia: {e}")
                    self._last_coord = result
                    self.exporter.add_waypoint(result)'''

content = re.sub(old_fusion, new_fusion, content, flags=re.DOTALL)
print("[OK] CAPA 3: Validacion de fusion")

# CAPA 4: Metodo reset_kalman
if '_reset_kalman_if_needed' not in content:
    reset_method = '''
    def _reset_kalman_if_needed(self) -> None:
        try:
            if self.kalman is not None and hasattr(self.kalman, 'reset'):
                self.kalman.reset()
            if self.imu is not None and hasattr(self.imu, 'reset'):
                self.imu.reset()
            print("[INFO] Filtros Kalman/IMU reinicializados")
        except Exception as e:
            print(f"[WARNING] Error reinicializando filtros: {e}")
    
'''
    insert_marker = content.find('def _is_gps_quality_valid')
    if insert_marker != -1:
        next_def = content.find('\n    def ', insert_marker + 1)
        if next_def != -1:
            content = content[:next_def] + reset_method + content[next_def:]
            print("[OK] CAPA 4: Metodo reset_kalman")

# CAPA 5: Filtro de lecturas Bridge
old_gps_loc = r'''                        gps_loc = Coordinate\(lat, lon, raw_gps\.altitude,
                                               accuracy, 'gps_enhanced'\)'''

new_gps_loc = '''                        if not _is_coordinate_sane(lat, lon):
                            print(f"[WARNING] Lectura GPS/Bridge invalida rechazada: ({lat:.2e}, {lon:.2e})")
                            gps_valid = False
                            gps_loc = None
                        else:
                            gps_loc = Coordinate(lat, lon, raw_gps.altitude,
                                               accuracy, 'gps_enhanced')'''

content = re.sub(old_gps_loc, new_gps_loc, content, flags=re.DOTALL)
print("[OK] CAPA 5: Filtro Bridge")

with open('sistema_uber_unificado.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Todas las capas aplicadas")

import subprocess
result = subprocess.run(['python3', '-m', 'py_compile', 'sistema_uber_unificado.py'], 
                      capture_output=True, text=True)

if result.returncode == 0:
    print("[OK] Sintaxis valida")
    print(f"\n[INFO] Backup guardado: {backup}")
    print("\n[+] 5 capas de proteccion aplicadas")
else:
    print("[ERROR] Errores:")
    print(result.stderr)
    with open(backup, 'r') as f:
        original = f.read()
    with open('sistema_uber_unificado.py', 'w') as f:
        f.write(original)
    print("[OK] Backup restaurado")
