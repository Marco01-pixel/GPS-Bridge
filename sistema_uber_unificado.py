echo "# FORCE_RENDER_DEPLOY" >> sistema_uber_unificado.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sistema_uber_unificado_CONSOLIDADO.py - Sistema monolitico Uber Daimon + GPS Symbiosis
Version consolidada con todas las modificaciones y fixes aplicados.
Compatible con Termux/Android. Python >= 3.10
"""
# ================================================================================
# SECCION 0: INTEGRACION DEL PUENTE UBER BRIDGE
# ================================================================================
try:
    from uber_bridge_client import UberBridgeClient, PromptBLEBroadcaster, apply_all_patches
    UBER_BRIDGE_AVAILABLE = True
except ImportError:
    UBER_BRIDGE_AVAILABLE = False
    print("[WARNING] uber_bridge_client no disponible. GPS nativo Android desactivado.")

class BridgeGPSProvider:
    """Proveedor GPS que usa UberBridgeClient para obtener ubicacion nativa Android."""
    def __init__(self, bridge_client=None):
        if UBER_BRIDGE_AVAILABLE:
            self.bridge = bridge_client or UberBridgeClient()
        else:
            self.bridge = None
        self._last_location = None
        self._history = None
        self._available = False
        if self.bridge:
            self._available = self.bridge.is_available()
        from collections import deque
        self._history = deque(maxlen=100)
    
    def get_location(self):
        if not self.bridge or not self._available:
            if self.bridge and time.time() % 30 < 1:
                self._available = self.bridge.is_available(force_check=True)
            return None
        coord_data = self.bridge.get_gps()
        if coord_data and hasattr(coord_data, 'is_valid') and coord_data.is_valid():
            self._last_location = coord_data
            if self._history is not None:
                self._history.append(coord_data)
            self._available = True
            return coord_data
        self._available = False
        return None
    
    def get_speed_kmh(self):
        if self._history is None or len(self._history) < 2:
            return 0.0
        d = self._history[-1].distance_to(self._history[-2])
        dt = max(0.1, self._history[-1].timestamp - self._history[-2].timestamp)
        return (d / dt) * 3.6 if dt > 0 else 0.0
    
    def is_available(self):
        return self._available

def patch_bluetooth_with_bridge(bt_scanner, bridge_client):
    if not bridge_client or not bridge_client.is_available():
        return False
    if not hasattr(bt_scanner, '_raw_scan'):
        return False
    original_raw_scan = bt_scanner._raw_scan
    def patched_raw_scan():
        if bridge_client.is_available():
            devices = bridge_client.scan_bluetooth()
            if devices:
                formatted = []
                for d in devices:
                    formatted.append({
                        'mac': d.get('mac', 'unknown'),
                        'name': d.get('name', 'unknown'),
                        'rssi': d.get('rssi', -60),
                        'timestamp': d.get('timestamp', time.time())
                    })
                if hasattr(bt_scanner, 'consecutive_failures'):
                    bt_scanner.consecutive_failures = 0
                if hasattr(bt_scanner, 'bluetooth_available'):
                    bt_scanner.bluetooth_available = True
                return formatted
        if hasattr(bt_scanner, 'bluetooth_available'):
            bt_scanner.bluetooth_available = False
        if hasattr(bt_scanner, 'consecutive_failures'):
            bt_scanner.consecutive_failures += 1
        return original_raw_scan()
    bt_scanner._raw_scan = patched_raw_scan
    return True

def patch_wifi_with_bridge(wifi_pos, bridge_client):
    if not bridge_client or not bridge_client.is_available():
        return False
    if not hasattr(wifi_pos, 'scan'):
        return False
    original_scan = wifi_pos.scan
    def patched_scan():
        if bridge_client.is_available():
            networks = bridge_client.scan_wifi()
            if networks:
                formatted = []
                for n in networks:
                    formatted.append({
                        'bssid': n.get('bssid', '').upper().strip(),
                        'ssid': n.get('ssid', ''),
                        'rssi': n.get('rssi', -60),
                        'frequency_mhz': n.get('frequency_mhz', 2400),
                        'timestamp': time.time()
                    })
                if hasattr(wifi_pos, 'consecutive_failures'):
                    wifi_pos.consecutive_failures = 0
                return formatted
        if hasattr(wifi_pos, 'consecutive_failures'):
            wifi_pos.consecutive_failures += 1
        return original_scan()
    wifi_pos.scan = patched_scan
    return True

def patch_cellular_with_bridge(cell_pos, bridge_client):
    if not bridge_client or not bridge_client.is_available():
        return False
    if not hasattr(cell_pos, 'scan'):
        return False
    original_scan = cell_pos.scan
    def patched_scan():
        if bridge_client.is_available():
            cells = bridge_client.get_cell_info()
            if cells:
                formatted = []
                for c in cells:
                    cell_type = c.get('type', 'lte')
                    cell_data = {
                        'type': cell_type,
                        'registered': c.get('registered', False),
                        'ci': c.get('ci', 0),
                        'tac': c.get('tac', 0),
                        'mcc': c.get('mcc', 0),
                        'mnc': c.get('mnc', 0),
                        'rsrp': c.get('rsrp', -100),
                        'rsrq': c.get('rsrq', -10),
                        'rssi': c.get('rssi', -90),
                        'bands': c.get('bands', []),
                        'timestamp': c.get('timestamp', time.time())
                    }
                    formatted.append(cell_data)
                if hasattr(cell_pos, 'consecutive_failures'):
                    cell_pos.consecutive_failures = 0
                return formatted
        if hasattr(cell_pos, 'consecutive_failures'):
            cell_pos.consecutive_failures += 1
        return original_scan()
    cell_pos.scan = patched_scan
    return True

def integrate_uber_bridge(gps_core):
    results = {
        'bridge_available': False,
        'gps_provider': False,
        'bluetooth': False,
        'wifi': False,
        'cellular': False
    }
    if not UBER_BRIDGE_AVAILABLE:
        return results
    bridge = UberBridgeClient()
    results['bridge_available'] = bridge.is_available()
    if not results['bridge_available']:
        return results
    try:
        bridge_provider = BridgeGPSProvider(bridge)
        if hasattr(gps_core, 'provider'):
            if not hasattr(gps_core, '_original_provider'):
                gps_core._original_provider = gps_core.provider
            gps_core.provider = bridge_provider
            results['gps_provider'] = True
    except Exception as e:
        pass
    try:
        if hasattr(gps_core, 'bluetooth'):
            results['bluetooth'] = patch_bluetooth_with_bridge(gps_core.bluetooth, bridge)
    except Exception:
        pass
    try:
        if hasattr(gps_core, 'wifi'):
            results['wifi'] = patch_wifi_with_bridge(gps_core.wifi, bridge)
    except Exception:
        pass
    try:
        if hasattr(gps_core, 'cellular'):
            results['cellular'] = patch_cellular_with_bridge(gps_core.cellular, bridge)
    except Exception:
        pass
    gps_core._uber_bridge = bridge
    return results

def auto_integrate_uber_bridge(symbiosis_instance):
    if not UBER_BRIDGE_AVAILABLE:
        return False
    if not hasattr(symbiosis_instance, 'gps'):
        return False
    bridge = UberBridgeClient()
    if not bridge.is_available():
        return False
    results = integrate_uber_bridge(symbiosis_instance.gps)
    return any(results.values())

# ================================================================================
# SECCION 1: IMPORTS ESTANDAR
# ================================================================================
import os
import sys
import json
import time
import uuid
import math
import random
import heapq
import signal
import shutil
import threading
import copy
import traceback
import pickle
import atexit
import logging
import subprocess
import hashlib
import socket
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union
from pathlib import Path
from fnmatch import fnmatch
from functools import lru_cache

# ================================================================================
# SECCION 2: CONFIGURACION DE LOGGING Y CONSTANTES GLOBALES
# ================================================================================
LOG_LEVEL = logging.INFO if not os.getenv('DEBUG') else logging.DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

EARTH_RADIUS_M = 6371000.0
METERS_PER_DEG_LAT = 111320.0
DEFAULT_GPS_TIMEOUT = 8
DEFAULT_BT_TIMEOUT = 8
DEFAULT_WIFI_TIMEOUT = 5
MAX_POSITION_HISTORY = 20
MAX_ACCURACY_HISTORY = 20
MAX_CONSECUTIVE_FAILURES = 15
ANTI_JUMP_MAX_SPEED_MS = 30.0
ANTI_JUMP_MAX_CORRECTION_DEG = 0.000027
MAX_PREDICTION_DRIFT_M = 100.0
GPS_QUALITY_AGE_SECONDS = 30.0
MAX_TRAJECTORY_POINTS = 10000

IS_TERMUX = os.getenv('TERMUX_VERSION') is not None or 'com.termux' in os.getenv('PATH', '')
DEBUG = os.getenv('DEBUG') is not None

# ================================================================================
# SECCION 3: DEPENDENCIAS OPCIONALES
# ================================================================================

# --- NUMPY ---
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

# --- REQUESTS ---
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# --- FLASK + CORS ---
# Inicializamos las variables globales
HAS_FLASK = False
app = None

try:
    from flask import Flask, jsonify, request
    from flask_cors import CORS
    # Creamos la instancia de la aplicación
    app = Flask(__name__)
    HAS_FLASK = True
except ImportError:
    # Si falla, mantenemos HAS_FLASK = False y app = None
    pass

# --- VERIFICACIÓN (opcional, para logs) ---
if HAS_FLASK:
    print("[OK] Flask y CORS cargados correctamente.")
else:
    print("[WARNING] Flask no disponible. El modo web estará desactivado.")

# ================================================================================
# SECCION 4: REGISTRO COMPARTIDO DE DATOS (thread-safe)
# ================================================================================
class SharedDataRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._callbacks: Dict[str, List[Tuple[str, Callable]]] = defaultdict(list)
    
    def set(self, key: str, value: Any, notify: bool = True) -> bool:
        with self._lock:
            try:
                self._data[key] = copy.deepcopy(value)
                if notify:
                    self._trigger_callbacks(key, value)
                return True
            except Exception:
                return False
    
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return copy.deepcopy(self._data.get(key, default))
    
    def on_change(self, key_pattern: str, callback: Callable) -> str:
        with self._lock:
            cid = str(hash(callback))[:8]
            self._callbacks[key_pattern].append((cid, callback))
            return cid
    
    def _trigger_callbacks(self, key: str, value: Any):
        for pattern, cbs in self._callbacks.items():
            if fnmatch(key, pattern):
                for _, cb in cbs:
                    try:
                        cb(key, value)
                    except Exception:
                        pass

# ================================================================================
# SECCION 5: COORDENADAS Y UTILIDADES GEOGRAFICAS
# ================================================================================
@dataclass
class Coordinate:
    latitude: float
    longitude: float
    altitude: float = 0.0
    accuracy: float = 0.0
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
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
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360.0) % 360.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'accuracy': self.accuracy,
            'source': self.source,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Coordinate':
        return cls(
            latitude=d.get('latitude', 0.0),
            longitude=d.get('longitude', 0.0),
            altitude=d.get('altitude', 0.0),
            accuracy=d.get('accuracy', 0.0),
            source=d.get('source', 'unknown'),
            timestamp=d.get('timestamp', time.time())
        )
    
    def is_valid(self) -> bool:
        return (-90.0 <= self.latitude <= 90.0 and
                -180.0 <= self.longitude <= 180.0 and
                self.accuracy >= 0.0)

def haversine(lat1, lon1, lat2, lon2) -> float:
    return Coordinate(lat1, lon1).distance_to(Coordinate(lat2, lon2))

# ================================================================================
# SECCION 6: UTILIDADES MATEMATICAS
# ================================================================================
class MathUtils:
    @staticmethod
    def meters_to_degrees_lat(meters: float) -> float:
        return meters / METERS_PER_DEG_LAT
    
    @staticmethod
    def meters_to_degrees_lon(meters: float, latitude: float) -> float:
        cos_lat = math.cos(math.radians(latitude))
        if abs(cos_lat) < 1e-10:
            return 0.0
        return meters / (METERS_PER_DEG_LAT * cos_lat)
    
    @staticmethod
    def degrees_lat_to_meters(degrees: float) -> float:
        return degrees * METERS_PER_DEG_LAT
    
    @staticmethod
    def degrees_lon_to_meters(degrees: float, latitude: float) -> float:
        return degrees * METERS_PER_DEG_LAT * math.cos(math.radians(latitude))
    
    @staticmethod
    def clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))
    
    @staticmethod
    def exponential_moving_average(current: float, new_value: float, alpha: float) -> float:
        return alpha * current + (1.0 - alpha) * new_value
    
    @staticmethod
    def calculate_variance(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)
    
    @staticmethod
    def median(values: List[float]) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 1:
            return sorted_vals[n // 2]
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0
    
    @staticmethod
    def normalize_angle(angle: float) -> float:
        return angle % 360.0
# ================================================================================
# SECCION 7: FILTRO DE KALMAN EXTENDIDO (EKF)
# ================================================================================
class ExtendedKalmanFilter:
    """EKF 6D: lat, lon, v_lat, v_lon, bias_lat, bias_lon.
    El filtro estima:
    - Posicion (lat, lon) en grados
    - Velocidad (v_lat, v_lon) en grados/segundo
    - Bias (bias_lat, bias_lon) en grados (error sistematico del GPS)
    El modelo dinamico es:
    - pos_k = pos_{k-1} + v_{k-1} * dt + bias_k
    - v_k = v_{k-1} + ruido
    - bias_k = bias_{k-1} + ruido (bias varia lentamente)
    """
    def __init__(self, dt: float = 0.5) -> None:
        self.dt = dt
        self.x = [0.0] * 6
        self.P = [0.0] * 36
        pos_uncertainty_deg = (4.0 / METERS_PER_DEG_LAT) ** 2
        vel_uncertainty = (0.5 / METERS_PER_DEG_LAT) ** 2
        bias_uncertainty = pos_uncertainty_deg * 0.5
        self.P[self._idx(0, 0)] = pos_uncertainty_deg
        self.P[self._idx(1, 1)] = pos_uncertainty_deg
        self.P[self._idx(2, 2)] = vel_uncertainty
        self.P[self._idx(3, 3)] = vel_uncertainty
        self.P[self._idx(4, 4)] = bias_uncertainty
        self.P[self._idx(5, 5)] = bias_uncertainty
        self.P_initial = self.P.copy()
        self.Q = [0.0] * 36
        self.q_pos = 1e-6
        self.q_vel = 0.01
        self.q_bias = 1e-8
        self.R = [0.0] * 4
        r_default = (10.0 / METERS_PER_DEG_LAT) ** 2
        self.R[0] = r_default
        self.R[3] = r_default
        self.F = [0.0] * 36
        self.initialized = False
        self.step_count = 0
        self._min_covariance = 1e-15
        self._max_covariance = 1e-2
        self._divergence_count = 0
        self._quality_smoothing = 0.5
        self.diag = {
            'innovations': deque(maxlen=20),
            'gains': deque(maxlen=20),
            'covariance_trace': deque(maxlen=20),
            'resets': 0,
            'divergence_events': 0,
            'pos_error_m': deque(maxlen=20),
            'bias_estimate': deque(maxlen=20)
        }

    def _idx(self, i: int, j: int) -> int:
        return i * 6 + j

    def _mat_mult_6x6_6x1(self, A: List[float], b: List[float]) -> List[float]:
        result = [0.0] * 6
        for i in range(6):
            for j in range(6):
                result[i] += A[self._idx(i, j)] * b[j]
        return result

    def _mat_mult_6x6_6x6(self, A: List[float], B: List[float]) -> List[float]:
        result = [0.0] * 36
        for i in range(6):
            for j in range(6):
                for k in range(6):
                    result[self._idx(i, j)] += A[self._idx(i, k)] * B[self._idx(k, j)]
        return result

    def _mat_transpose_6x6(self, A: List[float]) -> List[float]:
        result = [0.0] * 36
        for i in range(6):
            for j in range(6):
                result[self._idx(j, i)] = A[self._idx(i, j)]
        return result

    def _clamp_covariance(self) -> None:
        for i in range(6):
            val = self.P[self._idx(i, i)]
            if val < self._min_covariance:
                self.P[self._idx(i, i)] = self._min_covariance
                self._divergence_count += 1
            elif val > self._max_covariance:
                self.P[self._idx(i, i)] = self._max_covariance
                self._divergence_count += 1
            elif math.isnan(val) or math.isinf(val):
                self.P[self._idx(i, i)] = 1e-6
                self._divergence_count += 1
        if self._divergence_count > 50:
            for i in range(6):
                if self.P[self._idx(i, i)] < self._min_covariance * 10:
                    self.P[self._idx(i, i)] = self.P_initial[self._idx(i, i)]
            self._divergence_count = 0
            self.diag['resets'] += 1

    def _build_F(self) -> None:
        self.F = [0.0] * 36
        for i in range(6):
            self.F[self._idx(i, i)] = 1.0
        dt = self.dt
        self.F[self._idx(0, 2)] = dt
        self.F[self._idx(1, 3)] = dt

    def _build_Q(self) -> None:
        self.Q = [0.0] * 36
        dt = self.dt
        self.Q[self._idx(0, 0)] = self.q_pos * dt
        self.Q[self._idx(1, 1)] = self.q_pos * dt
        self.Q[self._idx(2, 2)] = self.q_vel * dt
        self.Q[self._idx(3, 3)] = self.q_vel * dt
        self.Q[self._idx(4, 4)] = self.q_bias * dt
        self.Q[self._idx(5, 5)] = self.q_bias * dt

    def _check_state_divergence(self) -> bool:
        for i in range(6):
            if math.isnan(self.x[i]) or math.isinf(self.x[i]):
                return True
        return False

    def predict(self) -> Tuple[float, float]:
        if not self.initialized:
            return (self.x[0], self.x[1])
        dt_effective = min(self.dt, 2.0)
        original_dt = self.dt
        self.dt = dt_effective
        self._build_F()
        self.dt = original_dt
        self.x = self._mat_mult_6x6_6x1(self.F, self.x)
        if self._check_state_divergence():
            self.x = [0.0] * 6
            self.diag['divergence_events'] += 1
            return (0.0, 0.0)
        self._build_Q()
        FP = self._mat_mult_6x6_6x6(self.F, self.P)
        Ft = self._mat_transpose_6x6(self.F)
        FPFt = self._mat_mult_6x6_6x6(FP, Ft)
        for i in range(36):
            self.P[i] = FPFt[i] + self.Q[i]
        if self.step_count > 10:
            epsilon = 1e-12
            for i in range(6):
                self.P[self._idx(i, i)] += epsilon
        self._clamp_covariance()
        return (self.x[0], self.x[1])

    def update(self, lat: float, lon: float, accuracy: Optional[float] = None) -> Tuple[float, float]:
        z = [lat, lon]
        if not self.initialized:
            self.x[0] = lat
            self.x[1] = lon
            self.x[4] = 0.0
            self.x[5] = 0.0
            self.initialized = True
            self.step_count = 1
            self.diag['bias_estimate'].append((0.0, 0.0))
            return (lat, lon)
        if accuracy is not None and accuracy > 0:
            accuracy_deg = max(0.01, accuracy / METERS_PER_DEG_LAT)
            r_val = accuracy_deg ** 2
            r_val = max(r_val, 1e-10)
            self.R[0] = r_val
            self.R[3] = r_val
        else:
            r_val = (10.0 / METERS_PER_DEG_LAT) ** 2
            self.R[0] = r_val
            self.R[3] = r_val
        y_lat = z[0] - (self.x[0] + self.x[4])
        y_lon = z[1] - (self.x[1] + self.x[5])
        innovation_magnitude = math.sqrt(
            (y_lat * METERS_PER_DEG_LAT) ** 2 +
            (y_lon * METERS_PER_DEG_LAT * math.cos(math.radians(self.x[0]))) ** 2
        )
        self.diag['innovations'].append(innovation_magnitude)
        if innovation_magnitude > 50.0:
            y_lat *= 0.3
            y_lon *= 0.3
        p00 = self.P[self._idx(0, 0)] + self.P[self._idx(0, 4)] + self.P[self._idx(4, 0)] + self.P[self._idx(4, 4)]
        p11 = self.P[self._idx(1, 1)] + self.P[self._idx(1, 5)] + self.P[self._idx(5, 1)] + self.P[self._idx(5, 5)]
        s_lat = max(p00 + self.R[0], 1e-12)
        s_lon = max(p11 + self.R[3], 1e-12)
        K = [0.0] * 12
        for i in range(6):
            p_hi_lat = self.P[self._idx(i, 0)] + self.P[self._idx(i, 4)]
            K[i * 2] = p_hi_lat / s_lat
            p_hi_lon = self.P[self._idx(i, 1)] + self.P[self._idx(i, 5)]
            K[i * 2 + 1] = p_hi_lon / s_lon
        avg_gain = sum(abs(k) for k in K) / len(K)
        self.diag['gains'].append(avg_gain)
        for i in range(6):
            self.x[i] += K[i * 2] * y_lat + K[i * 2 + 1] * y_lon
        if self._check_state_divergence():
            self.x = [0.0] * 6
            self.x[0] = lat
            self.x[1] = lon
            self.diag['divergence_events'] += 1
            return (lat, lon)
        P_new = self.P.copy()
        for i in range(6):
            for j in range(6):
                correction = 0.0
                correction += K[i * 2] * (self.P[self._idx(0, j)] + self.P[self._idx(4, j)])
                correction += K[i * 2 + 1] * (self.P[self._idx(1, j)] + self.P[self._idx(5, j)])
                P_new[self._idx(i, j)] -= correction
        self.P = P_new
        self._build_Q()
        for i in range(36):
            self.P[i] += self.Q[i] * 0.1
        self._clamp_covariance()
        trace = sum(self.P[self._idx(i, i)] for i in range(6))
        self.diag['covariance_trace'].append(trace)
        pos_cov = (self.P[self._idx(0, 0)] + self.P[self._idx(1, 1)]) / 2.0
        pos_error_m = math.sqrt(pos_cov) * METERS_PER_DEG_LAT
        self.diag['pos_error_m'].append(pos_error_m)
        self.diag['bias_estimate'].append((self.x[4], self.x[5]))
        if pos_cov < 1e-14 and self.step_count > 20:
            self.P[self._idx(0, 0)] += 1e-6
            self.P[self._idx(1, 1)] += 1e-6
            self.diag['resets'] += 1
        if pos_cov > 1e-3 and self.step_count > 50:
            for i in range(6):
                self.P[self._idx(i, i)] = min(self.P[self._idx(i, i)], self.P_initial[self._idx(i, i)] * 10)
            self.diag['resets'] += 1
        self.step_count += 1
        return (self.x[0], self.x[1])

    def get_velocity(self) -> Tuple[float, float]:
        return (self.x[2], self.x[3])

    def get_velocity_mps(self, latitude: float) -> Tuple[float, float]:
        v_lat_mps = self.x[2] * METERS_PER_DEG_LAT
        cos_lat = math.cos(math.radians(latitude))
        if abs(cos_lat) < 1e-10:
            cos_lat = 1e-10
        v_lon_mps = self.x[3] * METERS_PER_DEG_LAT * cos_lat
        return (v_lat_mps, v_lon_mps)

    def get_speed_mps(self, latitude: float) -> float:
        v_lat, v_lon = self.get_velocity_mps(latitude)
        return math.sqrt(v_lat**2 + v_lon**2)

    def get_speed_kmh(self, latitude: float) -> float:
        return self.get_speed_mps(latitude) * 3.6

    def get_bias(self) -> Tuple[float, float]:
        return (self.x[4], self.x[5])

    def get_bias_meters(self, latitude: float) -> Tuple[float, float]:
        bias_lat_m = self.x[4] * METERS_PER_DEG_LAT
        cos_lat = math.cos(math.radians(latitude))
        if abs(cos_lat) < 1e-10:
            cos_lat = 1e-10
        bias_lon_m = self.x[5] * METERS_PER_DEG_LAT * cos_lat
        return (bias_lat_m, bias_lon_m)

    def get_quality(self) -> float:
        if self.step_count < 5:
            return 0.3 + (self.step_count / 5.0) * 0.2
        p_lat = self.P[self._idx(0, 0)]
        p_lon = self.P[self._idx(1, 1)]
        p_lat_m2 = p_lat * (METERS_PER_DEG_LAT ** 2)
        p_lon_m2 = p_lon * (METERS_PER_DEG_LAT ** 2)
        avg_p_m2 = (p_lat_m2 + p_lon_m2) / 2.0
        std_dev_m = math.sqrt(max(avg_p_m2, 1e-10))
        if std_dev_m <= 1.0:
            quality = 0.95
        elif std_dev_m >= 100.0:
            quality = 0.05
        else:
            quality = 1.0 - (math.log10(std_dev_m) / math.log10(100.0))
        quality = max(0.05, min(0.95, quality))
        step_bonus = min(0.1, self.step_count / 1000.0)
        quality = min(1.0, quality + step_bonus)
        if self._divergence_count > 10:
            penalty = min(0.5, self._divergence_count / 100.0)
            quality = max(0.05, quality - penalty)
        alpha = 0.8
        self._quality_smoothing = alpha * self._quality_smoothing + (1.0 - alpha) * quality
        return MathUtils.clamp(self._quality_smoothing, 0.01, 1.0)

    def get_diagnostics(self) -> Dict[str, Any]:
        avg_innovation = 0.0
        if self.diag['innovations']:
            avg_innovation = sum(self.diag['innovations']) / len(self.diag['innovations'])
        avg_gain = 0.0
        if self.diag['gains']:
            avg_gain = sum(self.diag['gains']) / len(self.diag['gains'])
        avg_pos_error = 0.0
        if self.diag['pos_error_m']:
            avg_pos_error = sum(self.diag['pos_error_m']) / len(self.diag['pos_error_m'])
        last_bias = (0.0, 0.0)
        if self.diag['bias_estimate']:
            last_bias = self.diag['bias_estimate'][-1]
        return {
            'initialized': self.initialized,
            'step_count': self.step_count,
            'quality': self.get_quality(),
            'position_covariance_m2': (self.P[self._idx(0, 0)] + self.P[self._idx(1, 1)]) / 2.0 * METERS_PER_DEG_LAT**2,
            'position_std_m': math.sqrt((self.P[self._idx(0, 0)] + self.P[self._idx(1, 1)]) / 2.0) * METERS_PER_DEG_LAT,
            'velocity': self.get_velocity(),
            'velocity_mps': self.get_velocity_mps(self.x[0]) if self.initialized else (0, 0),
            'bias_deg': self.get_bias(),
            'bias_meters': self.get_bias_meters(self.x[0]) if self.initialized else (0, 0),
            'last_bias_meters': last_bias,
            'avg_innovation_m': avg_innovation,
            'avg_gain': avg_gain,
            'avg_pos_error_m': avg_pos_error,
            'divergence_count': self._divergence_count,
            'divergence_events': self.diag['divergence_events'],
            'resets': self.diag['resets'],
            'dt_current': self.dt
        }

    def set_dt(self, dt: float) -> None:
        self.dt = max(0.01, min(dt, 5.0))

    def reset(self, keep_bias: bool = False) -> None:
        saved_bias = (self.x[4], self.x[5]) if keep_bias else (0.0, 0.0)
        self.x = [0.0] * 6
        self.x[4] = saved_bias[0]
        self.x[5] = saved_bias[1]
        self.P = self.P_initial.copy()
        self.initialized = False
        self.step_count = 0
        self._divergence_count = 0
        self._quality_smoothing = 0.5
        self.diag['resets'] += 1
        self.diag['innovations'].clear()
        self.diag['gains'].clear()
        self.diag['covariance_trace'].clear()
        self.diag['pos_error_m'].clear()
        self.diag['bias_estimate'].clear()

# ================================================================================
# SECCION 8: CORRECTOR DIFERENCIAL (DGPS)
# ================================================================================
class DifferentialCorrector:
    def __init__(self, reference_station: Optional[Tuple[float, float]] = None) -> None:
        self.reference_station = reference_station
        self.reference_stations = []
        if reference_station:
            self.reference_stations.append({
                'position': reference_station,
                'weight': 1.0,
                'name': 'primary',
                'active': True
            })
        self.bias_history = deque(maxlen=100)
        self.bias_filtered = (0.0, 0.0)
        self.systematic_errors = {'lat': 0.0, 'lon': 0.0}
        self.is_calibrated = False
        self.alpha_smooth = 0.9
        self.alpha_adaptive = True
        self.max_correction_m = 50.0
        self.max_correction_deg = self.max_correction_m / METERS_PER_DEG_LAT
        self.outlier_detection_enabled = True
        self.outlier_std_threshold = 3.0
        self.bias_std = (0.0, 0.0)
        self.stats = {
            'corrections_applied': 0,
            'corrections_skipped': 0,
            'outliers_detected': 0,
            'total_correction_lat': 0.0,
            'total_correction_lon': 0.0,
            'avg_correction_m': 0.0,
            'last_correction_time': 0.0
        }
        self.accuracy_improvement_factors = {
            'high_confidence': 0.4,
            'medium_confidence': 0.55,
            'low_confidence': 0.75
        }

    def add_reference_station(self, position: Tuple[float, float], name: str = "", weight: float = 1.0) -> None:
        station = {
            'position': position,
            'weight': max(0.1, min(weight, 2.0)),
            'name': name or 'station_{}'.format(len(self.reference_stations)+1),
            'active': True,
            'added_at': time.time()
        }
        self.reference_stations.append(station)

    def _detect_outlier(self, bias_lat: float, bias_lon: float) -> bool:
        if not self.outlier_detection_enabled:
            return False
        if len(self.bias_history) < 10:
            return False
        recent = list(self.bias_history)[-20:]
        mean_lat = sum(b[0] for b in recent) / len(recent)
        mean_lon = sum(b[1] for b in recent) / len(recent)
        var_lat = sum((b[0] - mean_lat) ** 2 for b in recent) / len(recent)
        var_lon = sum((b[1] - mean_lon) ** 2 for b in recent) / len(recent)
        std_lat = math.sqrt(var_lat) if var_lat > 1e-15 else 1e-10
        std_lon = math.sqrt(var_lon) if var_lon > 1e-15 else 1e-10
        self.bias_std = (std_lat, std_lon)
        z_lat = abs(bias_lat - mean_lat) / std_lat if std_lat > 1e-10 else 0
        z_lon = abs(bias_lon - mean_lon) / std_lon if std_lon > 1e-10 else 0
        is_outlier = z_lat > self.outlier_std_threshold or z_lon > self.outlier_std_threshold
        if is_outlier:
            self.stats['outliers_detected'] += 1
        return is_outlier

    def _calculate_confidence(self) -> str:
        if not self.is_calibrated and len(self.bias_history) < 20:
            return 'low_confidence'
        if len(self.bias_history) < 10:
            return 'low_confidence'
        recent = list(self.bias_history)[-20:]
        if len(recent) < 5:
            return 'low_confidence'
        mean_lat = sum(b[0] for b in recent) / len(recent)
        mean_lon = sum(b[1] for b in recent) / len(recent)
        var_lat = sum((b[0] - mean_lat) ** 2 for b in recent) / len(recent)
        var_lon = sum((b[1] - mean_lon) ** 2 for b in recent) / len(recent)
        std_m_lat = math.sqrt(var_lat) * METERS_PER_DEG_LAT
        std_m_lon = math.sqrt(var_lon) * METERS_PER_DEG_LAT
        avg_std_m = (std_m_lat + std_m_lon) / 2.0
        if avg_std_m < 0.5 and self.is_calibrated:
            return 'high_confidence'
        elif avg_std_m < 2.0:
            return 'medium_confidence'
        else:
            return 'low_confidence'

    def correct(self, lat: float, lon: float, accuracy: float) -> Tuple[float, float, float]:
        lat_corr = lat
        lon_corr = lon
        if self.is_calibrated:
            lat_corr += self.systematic_errors['lat']
            lon_corr += self.systematic_errors['lon']
        active_stations = [s for s in self.reference_stations if s['active']]
        if active_stations:
            total_weight = 0.0
            weighted_bias_lat = 0.0
            weighted_bias_lon = 0.0
            for station in active_stations:
                ref_lat, ref_lon = station['position']
                weight = station['weight']
                station_bias_lat = ref_lat - lat_corr
                station_bias_lon = ref_lon - lon_corr
                max_corr_deg = self.max_correction_m / METERS_PER_DEG_LAT
                station_bias_lat = MathUtils.clamp(station_bias_lat, -max_corr_deg, max_corr_deg)
                station_bias_lon = MathUtils.clamp(station_bias_lon, -max_corr_deg, max_corr_deg)
                weighted_bias_lat += station_bias_lat * weight
                weighted_bias_lon += station_bias_lon * weight
                total_weight += weight
            if total_weight > 0:
                bias_lat = weighted_bias_lat / total_weight
                bias_lon = weighted_bias_lon / total_weight
                is_outlier = self._detect_outlier(bias_lat, bias_lon)
                if not is_outlier:
                    self.bias_history.append((bias_lat, bias_lon))
                    if len(self.bias_history) >= 5:
                        if len(self.bias_history) == 5:
                            avg_bias_lat = sum(b[0] for b in self.bias_history) / len(self.bias_history)
                            avg_bias_lon = sum(b[1] for b in self.bias_history) / len(self.bias_history)
                            self.bias_filtered = (avg_bias_lat, avg_bias_lon)
                        else:
                            if self.alpha_adaptive:
                                confidence = self._calculate_confidence()
                                if confidence == 'high_confidence':
                                    alpha = 0.95
                                elif confidence == 'medium_confidence':
                                    alpha = 0.85
                                else:
                                    alpha = 0.70
                            else:
                                alpha = self.alpha_smooth
                            last_bias = self.bias_filtered
                            new_bias_lat = alpha * last_bias[0] + (1.0 - alpha) * bias_lat
                            new_bias_lon = alpha * last_bias[1] + (1.0 - alpha) * bias_lon
                            self.bias_filtered = (new_bias_lat, new_bias_lon)
                    lat_corr += self.bias_filtered[0]
                    lon_corr += self.bias_filtered[1]
                    confidence = self._calculate_confidence()
                    improvement_factor = self.accuracy_improvement_factors[confidence]
                    accuracy *= improvement_factor
                    self.stats['corrections_applied'] += 1
                    self.stats['last_correction_time'] = time.time()
                else:
                    if self.bias_filtered != (0.0, 0.0):
                        lat_corr += self.bias_filtered[0]
                        lon_corr += self.bias_filtered[1]
                        accuracy *= self.accuracy_improvement_factors['medium_confidence']
                    self.stats['corrections_skipped'] += 1
        accuracy = max(0.3, accuracy)
        return lat_corr, lon_corr, accuracy

    def calibrate(self, known_position: Tuple[float, float], measured_position: Tuple[float, float]) -> None:
        self.systematic_errors['lat'] = known_position[0] - measured_position[0]
        self.systematic_errors['lon'] = known_position[1] - measured_position[1]
        self.is_calibrated = True

    def get_stats(self) -> Dict[str, Any]:
        return {
            'is_calibrated': self.is_calibrated,
            'reference_stations': len(self.reference_stations),
            'confidence': self._calculate_confidence(),
            'corrections_applied': self.stats['corrections_applied'],
            'corrections_skipped': self.stats['corrections_skipped'],
            'outliers_detected': self.stats['outliers_detected'],
        }

    def reset(self) -> None:
        self.bias_history.clear()
        self.bias_filtered = (0.0, 0.0)
        self.stats['corrections_applied'] = 0
        self.stats['corrections_skipped'] = 0
        self.stats['outliers_detected'] = 0

# ================================================================================
# SECCION 9: FUSION INERCIAL (IMU)
# ================================================================================
class IMUFusion:
    def __init__(self) -> None:
        self.last_position = None
        self.last_time = None
        self.velocity = (0.0, 0.0)
        self.acceleration = (0.0, 0.0)
        self.velocity_history = deque(maxlen=10)
        self.is_stationary = False
        self.stationary_threshold_mps = 0.5
        self.velocity_alpha = 0.7
        self.min_dt = 0.05

    def predict(self, lat: float, lon: float, dt: float) -> Tuple[float, float]:
        dt = max(self.min_dt, dt)
        if self.last_position is None or self.is_stationary:
            return (lat, lon)
        disp_lat_m = self.velocity[0] * dt + 0.5 * self.acceleration[0] * dt * dt
        disp_lon_m = self.velocity[1] * dt + 0.5 * self.acceleration[1] * dt * dt
        dlat = MathUtils.meters_to_degrees_lat(disp_lat_m)
        dlon = MathUtils.meters_to_degrees_lon(disp_lon_m, lat)
        return (lat + dlat, lon + dlon)

    def update(self, gps_lat: float, gps_lon: float, imu_lat: float, imu_lon: float) -> Tuple[float, float]:
        now = time.time()
        if self.last_time is not None and self.last_position is not None:
            dt = max(self.min_dt, now - self.last_time)
            prev_lat, prev_lon = self.last_position
            dlat_m = (gps_lat - prev_lat) * METERS_PER_DEG_LAT
            cos_lat = math.cos(math.radians((gps_lat + prev_lat) / 2.0))
            dlon_m = (gps_lon - prev_lon) * METERS_PER_DEG_LAT * cos_lat
            new_v_lat = dlat_m / dt
            new_v_lon = dlon_m / dt
            self.velocity = (
                self.velocity_alpha * new_v_lat + (1.0 - self.velocity_alpha) * self.velocity[0],
                self.velocity_alpha * new_v_lon + (1.0 - self.velocity_alpha) * self.velocity[1]
            )
            speed = math.sqrt(self.velocity[0] ** 2 + self.velocity[1] ** 2)
            self.is_stationary = speed < self.stationary_threshold_mps
            if self.is_stationary:
                gps_weight = 0.95
            else:
                speed = math.sqrt(self.velocity[0] ** 2 + self.velocity[1] ** 2)
                if speed < 2.0:
                    gps_weight = 0.85
                elif speed > 15.0:
                    gps_weight = 0.60
                else:
                    gps_weight = 0.85 - (speed - 2.0) / 13.0 * 0.25
            imu_weight = 1.0 - gps_weight
            fused_lat = gps_weight * gps_lat + imu_weight * imu_lat
            fused_lon = gps_weight * gps_lon + imu_weight * imu_lon
            self.last_position = (fused_lat, fused_lon)
            self.last_time = now
            return (fused_lat, fused_lon)
        self.last_position = (gps_lat, gps_lon)
        self.last_time = now
        return (gps_lat, gps_lon)

    def get_speed_ms(self) -> float:
        return math.sqrt(self.velocity[0] ** 2 + self.velocity[1] ** 2)

    def reset(self) -> None:
        self.last_position = None
        self.last_time = None
        self.velocity = (0.0, 0.0)
        self.acceleration = (0.0, 0.0)
        self.velocity_history.clear()
        self.is_stationary = True

# ================================================================================
# SECCION 10: BLUETOOTH AVANZADO
# ================================================================================
class AdvancedBluetoothScanner:
    """Escáner Bluetooth avanzado con filtros Kalman, fingerprinting y aprendizaje automatico."""
    def __init__(self) -> None:
        self.known_beacons: Dict[str, Dict[str, Any]] = {}
        self.rssi_history: Dict[str, deque] = {}
        self.kalman_filters: Dict[str, Dict[str, float]] = {}
        self.fingerprint_db: Dict[str, Dict[str, Any]] = {}
        self.last_location: Optional[Tuple[float, float]] = None
        self.auto_learn_enabled: bool = False
        self.min_rssi: int = -95
        self.max_rssi: int = -30
        self.multipath_variance_threshold: float = 25.0
        self.bluetooth_available: bool = True
        self.bluetooth_checked: bool = False
        self.last_scan_error: Optional[str] = None
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 10
        self.scan_cache: List[Dict] = []
        self.scan_cache_time: float = 0
        self.scan_cache_duration: float = 2.0

    def enable_auto_learning(self, enabled: bool = True) -> None:
        self.auto_learn_enabled = enabled

    def add_beacon(self, mac: str, lat: float, lon: float, name: str = "",
                   tx_power: int = -59, env_factor: float = 2.5) -> None:
        mac = mac.upper().strip()
        self.known_beacons[mac] = {
            'lat': lat, 'lon': lon, 'name': name,
            'tx_power': tx_power, 'confidence': 0.9, 'env_factor': env_factor
        }

    def _normalize_mac(self, mac: str) -> str:
        if not mac:
            return "unknown"
        return mac.upper().strip().replace(':', '-')

    def _get_kalman_filter(self, mac: str) -> Dict[str, float]:
        mac = self._normalize_mac(mac)
        if mac not in self.kalman_filters:
            self.kalman_filters[mac] = {
                'rssi': -70.0, 'variance': 25.0,
                'process_noise': 0.5, 'measurement_noise': 4.0
            }
        return self.kalman_filters[mac]

    def _filter_rssi_kalman(self, mac: str, rssi: int) -> float:
        kf = self._get_kalman_filter(mac)
        predicted_rssi = kf['rssi']
        predicted_variance = kf['variance'] + kf['process_noise']
        kalman_gain = predicted_variance / (predicted_variance + kf['measurement_noise'])
        filtered_rssi = predicted_rssi + kalman_gain * (rssi - predicted_rssi)
        filtered_variance = (1.0 - kalman_gain) * predicted_variance
        kf['rssi'] = filtered_rssi
        kf['variance'] = filtered_variance
        return filtered_rssi

    def _moving_average_rssi(self, mac: str, rssi: float, window: int = 5) -> float:
        mac = self._normalize_mac(mac)
        if mac not in self.rssi_history:
            self.rssi_history[mac] = deque(maxlen=window)
        self.rssi_history[mac].append(rssi)
        return sum(self.rssi_history[mac]) / len(self.rssi_history[mac])

    def _rssi_to_distance_advanced(self, rssi: float, tx_power: int = -59,
                                    env_factor: float = 2.0) -> float:
        if rssi >= 0 or rssi < self.min_rssi:
            return -1.0
        exponent = (tx_power - rssi) / (10.0 * env_factor)
        distance = 10.0 ** exponent
        return MathUtils.clamp(distance, 0.1, 100.0)

    def _detect_multipath(self, rssi_history_list: List[float]) -> bool:
        if len(rssi_history_list) < 4:
            return False
        variance = MathUtils.calculate_variance(rssi_history_list)
        return variance > self.multipath_variance_threshold

    def _check_bluetooth_available(self) -> bool:
        if self.bluetooth_checked:
            return self.bluetooth_available
        self.bluetooth_checked = True
        try:
            result = subprocess.run(
                ['termux-bluetooth-status'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if data.get('bluetooth_supported') is False:
                        self.bluetooth_available = False
                        return False
                    if data.get('enabled') is False:
                        subprocess.run(['termux-bluetooth-enable'],
                                       capture_output=True, timeout=3)
                        time.sleep(1)
                        return True
                    self.bluetooth_available = True
                    return True
                except json.JSONDecodeError:
                    pass
            result = subprocess.run(
                ['termux-bluetooth-scan', '--duration', '1'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                error_msg = result.stdout + result.stderr
                if "bluetooth_supported" in error_msg or "Failure" in error_msg:
                    self.bluetooth_available = False
                    return False
            self.bluetooth_available = True
            return True
        except Exception:
            return False

    def _parse_bt_output(self, stdout: str) -> List[Dict]:
        devices: List[Dict] = []
        try:
            json_data = json.loads(stdout)
            if isinstance(json_data, dict):
                if json_data.get('bluetooth_supported') is False:
                    self.bluetooth_available = False
                    return []
                device_list = json_data.get('devices', json_data.get('results', []))
                if device_list:
                    for item in device_list:
                        mac = item.get('address', item.get('mac', 'unknown'))
                        if mac and mac != 'unknown':
                            devices.append({
                                'mac': self._normalize_mac(mac),
                                'name': item.get('name', item.get('device_name', 'unknown')),
                                'rssi': int(item.get('rssi', -60)),
                                'timestamp': time.time()
                            })
            elif isinstance(json_data, list):
                for item in json_data:
                    mac = item.get('address', item.get('mac', 'unknown'))
                    if mac and mac != 'unknown':
                        devices.append({
                            'mac': self._normalize_mac(mac),
                            'name': item.get('name', item.get('device_name', 'unknown')),
                            'rssi': int(item.get('rssi', -60)),
                            'timestamp': time.time()
                        })
            if devices:
                return devices
        except json.JSONDecodeError:
            pass
        import re
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            rssi = -60
            mac = 'unknown'
            name = 'unknown'
            rssi_match = re.search(r'rssi[:\s]+(-?\d+)', line, re.IGNORECASE)
            if not rssi_match:
                rssi_match = re.search(r'(-\d+)\s*$', line)
            if rssi_match:
                rssi = int(rssi_match.group(1))
                rssi = MathUtils.clamp(rssi, self.min_rssi, self.max_rssi)
            mac_match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', line)
            if mac_match:
                mac = mac_match.group(0).upper()
                if mac != 'unknown':
                    name_part = line.split(mac)[-1] if mac in line else line
                    name_part = re.sub(r'[-\d]+\s*$', '', name_part).strip()
                    if name_part and name_part != line:
                        name = name_part[:30]
                    devices.append({
                        'mac': self._normalize_mac(mac),
                        'name': name or 'unknown',
                        'rssi': rssi,
                        'timestamp': time.time()
                    })
        return devices

    def _raw_scan(self) -> List[Dict]:
        if not self._check_bluetooth_available():
            return []
        now = time.time()
        if self.scan_cache and (now - self.scan_cache_time) < self.scan_cache_duration:
            return self.scan_cache.copy()
        devices: List[Dict] = []
        try:
            durations = ['4', '3', '2']
            for duration in durations:
                try:
                    result = subprocess.run(
                        ['termux-bluetooth-scan', '--duration', duration],
                        capture_output=True, text=True, timeout=int(duration) + 3
                    )
                    if result.returncode != 0:
                        continue
                    parsed = self._parse_bt_output(result.stdout)
                    if parsed:
                        devices = parsed
                        break
                except Exception:
                    continue
            if devices:
                self.consecutive_failures = 0
                self.last_scan_error = None
                self.scan_cache = devices
                self.scan_cache_time = now
                return devices
            else:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.bluetooth_available = False
        except subprocess.TimeoutExpired as e:
            self.last_scan_error = str(e)
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.bluetooth_available = False
        except Exception as e:
            self.last_scan_error = str(e)
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.bluetooth_available = False
        return devices

    def scan_advanced(self) -> List[Dict]:
        raw_devices = self._raw_scan()
        if not raw_devices:
            return []
        processed: List[Dict] = []
        for device in raw_devices:
            mac = device['mac']
            raw_rssi = MathUtils.clamp(device['rssi'], self.min_rssi, self.max_rssi)
            if raw_rssi < self.min_rssi:
                continue
            filtered_rssi = self._filter_rssi_kalman(mac, raw_rssi)
            smoothed_rssi = self._moving_average_rssi(mac, filtered_rssi)
            is_multipath = False
            if mac in self.rssi_history and len(self.rssi_history[mac]) >= 4:
                recent_raw = list(self.rssi_history[mac])[-4:]
                is_multipath = self._detect_multipath(recent_raw)
            if is_multipath:
                continue
            beacon = self.known_beacons.get(mac, {})
            tx_power = beacon.get('tx_power', -59)
            env_factor = beacon.get('env_factor', 2.5)
            distance = self._rssi_to_distance_advanced(smoothed_rssi, tx_power, env_factor)
            if distance < 0:
                continue
            processed.append({
                'mac': mac,
                'name': device.get('name', 'unknown'),
                'rssi': smoothed_rssi,
                'rssi_raw': raw_rssi,
                'distance': distance,
                'multipath_detected': is_multipath,
                'timestamp': time.time()
            })
        processed.sort(key=lambda x: x['distance'])
        return processed

    def _fingerprint_similarity(self, fp1: Dict[str, float], fp2: Dict[str, float]) -> float:
        common_macs = set(fp1.keys()) & set(fp2.keys())
        if not common_macs:
            return 0.0
        rssi_diff = 0.0
        total_weight = 0.0
        for mac in common_macs:
            weight = max(0.1, 1.0 - abs(fp1[mac] + 30) / 100.0)
            diff = abs(fp1[mac] - fp2[mac])
            rssi_diff += weight * min(1.0, diff / 20.0)
            total_weight += weight
        if total_weight <= 0:
            return 0.0
        similarity = 1.0 - (rssi_diff / total_weight)
        coverage_bonus = min(1.0, len(common_macs) / 8.0)
        return similarity * 0.6 + coverage_bonus * 0.4

    def get_location_by_fingerprint(self, scan_result: List[Dict]) -> Optional[Tuple[float, float, float]]:
        if not self.fingerprint_db or not scan_result:
            return None
        strong_beacons = [d for d in scan_result if d['rssi'] > -80]
        if len(strong_beacons) < 3:
            return None
        current_fp = {d['mac']: d['rssi'] for d in strong_beacons}
        best_match = None
        best_score = -1.0
        for fp_name, fp_data in self.fingerprint_db.items():
            score = self._fingerprint_similarity(current_fp, fp_data['fingerprint'])
            if score > best_score and score > 0.5:
                best_score = score
                best_match = fp_data
        if best_match:
            return (best_match['lat'], best_match['lon'], best_score)
        return None

    def trilateration_weighted(self, points: List[Dict]) -> Tuple[float, float, float]:
        if not points:
            return (0.0, 0.0, 999.0)
        if len(points) == 1:
            return (points[0]['lat'], points[0]['lon'], points[0]['distance'])
        valid_points = [p for p in points if p.get('distance', 999) < 50.0]
        if not valid_points:
            valid_points = points
        total_weight = 0.0
        weighted_lat = 0.0
        weighted_lon = 0.0
        for p in valid_points:
            dist = max(0.5, p['distance'])
            confidence = p.get('confidence', 0.5)
            weight = (1.0 / (dist ** 2)) * confidence
            weighted_lat += p['lat'] * weight
            weighted_lon += p['lon'] * weight
            total_weight += weight
        if total_weight > 0:
            lat = weighted_lat / total_weight
            lon = weighted_lon / total_weight
            distances = [p['distance'] for p in valid_points]
            avg_distance = sum(distances) / len(distances)
            return (lat, lon, avg_distance)
        return (valid_points[0]['lat'], valid_points[0]['lon'], valid_points[0]['distance'])

    def learn_beacon_automatically(self, mac: str, lat: float, lon: float,
                                    confidence: float = 0.5) -> None:
        mac = self._normalize_mac(mac)
        now = time.time()
        if mac not in self.known_beacons:
            self.known_beacons[mac] = {
                'lat': lat, 'lon': lon, 'name': 'auto_learned',
                'tx_power': -59, 'confidence': confidence,
                'env_factor': 2.5, 'discovered_at': now,
                'update_count': 1, 'last_seen': now
            }
        else:
            beacon = self.known_beacons[mac]
            old_conf = beacon.get('confidence', 0.5)
            new_conf = min(0.95, old_conf + confidence * 0.1)
            total_conf = old_conf + confidence
            if total_conf > 0:
                beacon['lat'] = (beacon['lat'] * old_conf + lat * confidence) / total_conf
                beacon['lon'] = (beacon['lon'] * old_conf + lon * confidence) / total_conf
                beacon['confidence'] = new_conf
                beacon['update_count'] = beacon.get('update_count', 0) + 1
                beacon['last_seen'] = now

    def add_fingerprint(self, name: str, lat: float, lon: float,
                        scan_result: List[Dict]) -> None:
        quality_scan = [d for d in scan_result
                        if d['rssi'] > -85 and not d.get('multipath_detected', False)]
        fingerprint = {d['mac']: d['rssi'] for d in quality_scan}
        self.fingerprint_db[name] = {
            'lat': lat, 'lon': lon, 'fingerprint': fingerprint,
            'created_at': time.time(), 'beacon_count': len(fingerprint)
        }

    def get_best_location(self, scan_result: List[Dict]) -> Optional[Tuple[float, float, float]]:
        if not scan_result:
            return None
        fp_location = self.get_location_by_fingerprint(scan_result)
        if fp_location and fp_location[2] > 0.7:
            return fp_location
        points_for_trilateration = []
        for device in scan_result:
            mac = device['mac']
            if mac in self.known_beacons:
                beacon = self.known_beacons[mac]
                points_for_trilateration.append({
                    'lat': beacon['lat'], 'lon': beacon['lon'],
                    'distance': device['distance'],
                    'confidence': beacon.get('confidence', 0.5) * (
                        1.0 if not device.get('multipath_detected') else 0.3)
                })
        if len(points_for_trilateration) >= 2:
            result = self.trilateration_weighted(points_for_trilateration)
            if fp_location and fp_location[2] > 0.5:
                return fp_location
            return result
        if points_for_trilateration:
            p = points_for_trilateration[0]
            return (p['lat'], p['lon'], p['distance'])
        return None

    def cleanup_old_beacons(self, max_age_hours: float = 168.0) -> int:
        now = time.time()
        max_age_sec = max_age_hours * 3600
        to_remove: List[str] = []
        for mac, beacon in self.known_beacons.items():
            if beacon.get('name') == 'auto_learned':
                last_seen = beacon.get('last_seen', beacon.get('discovered_at', 0))
                if now - last_seen > max_age_sec:
                    to_remove.append(mac)
        for mac in to_remove:
            del self.known_beacons[mac]
        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        return {
            'known_beacons': len(self.known_beacons),
            'auto_learn_enabled': self.auto_learn_enabled,
            'fingerprints': len(self.fingerprint_db),
            'bluetooth_available': self.bluetooth_available,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_scan_error,
            'kalman_filters': len(self.kalman_filters)
        }

    def reset(self) -> None:
        self.rssi_history.clear()
        self.kalman_filters.clear()
        self.consecutive_failures = 0
        self.last_scan_error = None
        self.bluetooth_available = True
        self.bluetooth_checked = False
        self.scan_cache.clear()

# ================================================================================
# SECCION 11: WIFI POSITIONING
# ================================================================================
class WiFiPositioning:
    """Posicionamiento por redes WiFi con aprendizaje automatico."""
    def __init__(self) -> None:
        self.known_networks: Dict[str, Dict[str, Any]] = {}
        self.default_tx_power: float = -40.0
        self.path_loss_exponent: float = 3.0
        self.scan_cache: List[Dict] = []
        self.scan_cache_time: float = 0
        self.scan_cache_duration: float = 3.0
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 10
        self.last_scan_error: Optional[str] = None
        self.scans_performed: int = 0
        self.networks_learned: int = 0

    def add_network(self, bssid: str, lat: float, lon: float, ssid: str = "",
                    tx_power: Optional[float] = None, auto_learned: bool = False) -> None:
        bssid = bssid.upper().strip()
        if not bssid or len(bssid) < 10:
            return
        self.known_networks[bssid] = {
            'lat': lat, 'lon': lon, 'ssid': ssid or 'unknown',
            'tx_power': tx_power or self.default_tx_power,
            'auto_learned': auto_learned,
            'added_at': time.time(),
            'last_seen': time.time()
        }
        if auto_learned:
            self.networks_learned += 1

    def scan(self) -> List[Dict]:
        now = time.time()
        if self.scan_cache and (now - self.scan_cache_time) < self.scan_cache_duration:
            return self.scan_cache.copy()
        networks: List[Dict] = []
        try:
            result = subprocess.run(
                ['termux-wifi-scaninfo'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        for ap in data:
                            bssid = ap.get('bssid', '').upper().strip()
                            if bssid:
                                networks.append({
                                    'bssid': bssid,
                                    'ssid': ap.get('ssid', ''),
                                    'rssi': MathUtils.clamp(ap.get('rssi', -60), -100, -10),
                                    'frequency': ap.get('frequency_mhz', ap.get('frequency', 2400)),
                                    'timestamp': now
                                })
                    elif isinstance(data, dict):
                        ap_list = data.get('data', data.get('results', []))
                        if isinstance(ap_list, list):
                            for ap in ap_list:
                                bssid = ap.get('bssid', '').upper().strip()
                                if bssid:
                                    networks.append({
                                        'bssid': bssid,
                                        'ssid': ap.get('ssid', ''),
                                        'rssi': MathUtils.clamp(ap.get('rssi', -60), -100, -10),
                                        'frequency': ap.get('frequency_mhz', ap.get('frequency', 2400)),
                                        'timestamp': now
                                    })
                except json.JSONDecodeError:
                    import re
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        bssid_match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', line, re.IGNORECASE)
                        if bssid_match:
                            bssid = bssid_match.group(0).upper().strip()
                            ssid = ''
                            rssi = -60
                            freq = 2400
                            ssid_match = re.search(r'"ssid":\s*"([^"]+)"', line)
                            if ssid_match:
                                ssid = ssid_match.group(1)
                            rssi_match = re.search(r'"rssi":\s*(-?\d+)', line)
                            if rssi_match:
                                rssi = int(rssi_match.group(1))
                            freq_match = re.search(r'"frequency_mhz":\s*(\d+)', line)
                            if freq_match:
                                freq = int(freq_match.group(1))
                            networks.append({
                                'bssid': bssid,
                                'ssid': ssid,
                                'rssi': MathUtils.clamp(rssi, -100, -10),
                                'frequency': freq,
                                'timestamp': now
                            })
                self.consecutive_failures = 0
                self.last_scan_error = None
            else:
                self.consecutive_failures += 1
        except subprocess.TimeoutExpired as e:
            self.consecutive_failures += 1
            self.last_scan_error = str(e)
        except Exception as e:
            self.consecutive_failures += 1
            self.last_scan_error = str(e)
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.consecutive_failures = 0
            try:
                subprocess.run(['svc', 'wifi', 'disable'], capture_output=True, timeout=2)
                time.sleep(1)
                subprocess.run(['svc', 'wifi', 'enable'], capture_output=True, timeout=2)
                time.sleep(2)
            except Exception:
                pass
        self.scan_cache = networks
        self.scan_cache_time = now
        self.scans_performed += 1
        return networks

    def _rssi_to_distance(self, rssi: float, tx_power: float,
                          frequency_mhz: float = 2400) -> float:
        if rssi >= 0:
            return 50.0
        freq_factor = 2.0 if frequency_mhz > 4000 else 1.0
        exponent = (tx_power - rssi) / (10.0 * self.path_loss_exponent * freq_factor)
        distance = 10.0 ** exponent
        return MathUtils.clamp(distance, 1.0, 100.0)

    def get_location(self, networks: List[Dict]) -> Optional[Tuple[float, float, float]]:
        if not networks or not self.known_networks:
            return None
        matched: List[Dict] = []
        for net in networks:
            bssid = net.get('bssid', '')
            if bssid and bssid in self.known_networks:
                ap = self.known_networks[bssid]
                rssi = net.get('rssi', -60)
                tx_power = ap.get('tx_power', self.default_tx_power)
                freq = net.get('frequency', 2400)
                distance = self._rssi_to_distance(rssi, tx_power, freq)
                signal_quality = MathUtils.clamp((rssi + 100) / 70.0, 0.1, 1.0)
                distance_confidence = max(0.1, 1.0 - distance / 50.0)
                confidence = signal_quality * distance_confidence
                if ap.get('auto_learned', False):
                    confidence *= 0.8
                matched.append({
                    'lat': ap['lat'],
                    'lon': ap['lon'],
                    'distance': distance,
                    'confidence': confidence,
                    'rssi': rssi,
                    'ssid': ap.get('ssid', 'unknown')
                })
        if not matched:
            return None
        matched.sort(key=lambda x: x['confidence'], reverse=True)
        if len(matched) >= 2:
            best_nets = matched[:3]
            total_weight = sum(m['confidence'] for m in best_nets)
            if total_weight > 0:
                lat = sum(m['lat'] * m['confidence'] for m in best_nets) / total_weight
                lon = sum(m['lon'] * m['confidence'] for m in best_nets) / total_weight
                avg_dist = sum(m['distance'] * m['confidence'] for m in best_nets) / total_weight
                return (lat, lon, avg_dist)
        return (matched[0]['lat'], matched[0]['lon'], matched[0]['distance'])

    def learn_network_automatically(self, bssid: str, lat: float, lon: float,
                                     ssid: str = "", rssi: float = -60) -> None:
        bssid = bssid.upper().strip()
        if not bssid or len(bssid) < 10:
            return
        if bssid not in self.known_networks:
            self.known_networks[bssid] = {
                'lat': lat,
                'lon': lon,
                'ssid': ssid or 'auto_learned',
                'tx_power': self.default_tx_power,
                'auto_learned': True,
                'added_at': time.time(),
                'last_seen': time.time(),
                'first_rssi': rssi,
                'update_count': 1
            }
            self.networks_learned += 1
        else:
            net = self.known_networks[bssid]
            old_lat = net['lat']
            old_lon = net['lon']
            old_conf = 0.5
            new_conf = 0.3
            total_conf = old_conf + new_conf
            net['lat'] = (old_lat * old_conf + lat * new_conf) / total_conf
            net['lon'] = (old_lon * old_conf + lon * new_conf) / total_conf
            net['last_seen'] = time.time()
            net['update_count'] = net.get('update_count', 0) + 1
            net['tx_power'] = max(net.get('tx_power', self.default_tx_power), rssi + 20)

    def get_stats(self) -> Dict[str, Any]:
        auto_learned = sum(1 for n in self.known_networks.values() if n.get('auto_learned', False))
        return {
            'known_networks': len(self.known_networks),
            'networks_learned': self.networks_learned,
            'auto_learned': auto_learned,
            'scans_performed': self.scans_performed,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_scan_error,
            'scan_cache_size': len(self.scan_cache)
        }

    def cleanup_old_networks(self, max_age_days: float = 30.0) -> int:
        now = time.time()
        max_age_sec = max_age_days * 86400
        to_remove: List[str] = []
        for bssid, net in self.known_networks.items():
            if net.get('auto_learned', False):
                last_seen = net.get('last_seen', net.get('added_at', 0))
                if now - last_seen > max_age_sec:
                    to_remove.append(bssid)
        for bssid in to_remove:
            del self.known_networks[bssid]
        return len(to_remove)

# ================================================================================
# SECCION 12: POSICIONAMIENTO POR TELEFONIA CELULAR (LTE/GSM)
# ================================================================================
class CellularPositioning:
    """Posicionamiento por torres celulares con aprendizaje automatico."""
    def __init__(self) -> None:
        self.known_towers: Dict[str, Dict[str, Any]] = {}
        self.last_scan_result: List[Dict] = []
        self.last_scan_time: float = 0
        self.scan_cache_duration: float = 5.0
        self.min_signal_dbm: int = -120
        self.max_distance_m: float = 5000.0
        self.scans_performed: int = 0
        self.towers_learned: int = 0
        self.auto_learn_enabled: bool = False
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 10
        self.last_scan_error: Optional[str] = None

    def add_tower(self, ci: int, tac: int, mcc: int, mnc: int,
                  lat: float, lon: float, radius_m: float = 500.0,
                  confidence: float = 0.5, auto_learned: bool = False) -> None:
        tower_id = f"{mcc}-{mnc}-{tac}-{ci}"
        self.known_towers[tower_id] = {
            'ci': ci, 'tac': tac, 'mcc': mcc, 'mnc': mnc,
            'lat': lat, 'lon': lon, 'radius_m': radius_m,
            'confidence': confidence, 'added_at': time.time(),
            'last_seen': time.time(), 'auto_learned': auto_learned
        }
        self.towers_learned = len(self.known_towers)

    def scan(self) -> List[Dict]:
        now = time.time()
        if now - self.last_scan_time < self.scan_cache_duration:
            return self.last_scan_result.copy()
        cells: List[Dict] = []
        try:
            result = subprocess.run(
                ['termux-telephony-cellinfo'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        for cell in data:
                            cell_type = cell.get('type', '').lower()
                            if cell_type == 'lte' or cell_type == 'gsm' or cell_type == 'wcdma':
                                rsrp = cell.get('rsrp', cell.get('dbm', -100))
                                if rsrp >= self.min_signal_dbm:
                                    cells.append({
                                        'type': cell_type,
                                        'registered': cell.get('registered', False),
                                        'ci': cell.get('ci', 0),
                                        'tac': cell.get('tac', 0),
                                        'mcc': cell.get('mcc', 0),
                                        'mnc': cell.get('mnc', 0),
                                        'rsrp': rsrp,
                                        'rsrq': cell.get('rsrq', -10),
                                        'rssi': cell.get('rssi', -90),
                                        'bands': cell.get('bands', []),
                                        'timestamp': now
                                    })
                        cells.sort(key=lambda x: x['rsrp'], reverse=True)
                except json.JSONDecodeError:
                    import re
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        ci_match = re.search(r'"ci":\s*(\d+)', line)
                        tac_match = re.search(r'"tac":\s*(\d+)', line)
                        mcc_match = re.search(r'"mcc":\s*(\d+)', line)
                        mnc_match = re.search(r'"mnc":\s*(\d+)', line)
                        rsrp_match = re.search(r'"rsrp":\s*(-?\d+)', line)
                        if ci_match and tac_match and mcc_match and mnc_match:
                            cell = {
                                'type': 'lte',
                                'registered': 'registered' in line and 'true' in line.lower(),
                                'ci': int(ci_match.group(1)),
                                'tac': int(tac_match.group(1)),
                                'mcc': int(mcc_match.group(1)),
                                'mnc': int(mnc_match.group(1)),
                                'rsrp': int(rsrp_match.group(1)) if rsrp_match else -100,
                                'rsrq': -10,
                                'rssi': -90,
                                'bands': [],
                                'timestamp': now
                            }
                            if cell['rsrp'] >= self.min_signal_dbm:
                                cells.append(cell)
                self.consecutive_failures = 0
                self.last_scan_error = None
            else:
                self.consecutive_failures += 1
        except subprocess.TimeoutExpired as e:
            self.consecutive_failures += 1
            self.last_scan_error = str(e)
        except Exception as e:
            self.consecutive_failures += 1
            self.last_scan_error = str(e)
        self.last_scan_result = cells
        self.last_scan_time = now
        self.scans_performed += 1
        return cells

    def _estimate_distance_from_signal(self, rsrp: float, rsrq: float) -> Tuple[float, float]:
        if rsrp > -80:
            distance = 100.0
            confidence = 0.8
        elif rsrp > -90:
            ratio = (-80 - rsrp) / 10.0
            distance = 100.0 + ratio * 400.0
            confidence = 0.7
        elif rsrp > -100:
            ratio = (-90 - rsrp) / 10.0
            distance = 500.0 + ratio * 1500.0
            confidence = 0.5
        elif rsrp > -110:
            ratio = (-100 - rsrp) / 10.0
            distance = 2000.0 + ratio * 3000.0
            confidence = 0.3
        else:
            distance = 5000.0
            confidence = 0.1
        if rsrq > -5:
            confidence *= 1.2
        elif rsrq < -15:
            confidence *= 0.7
        return (MathUtils.clamp(distance, 50.0, 5000.0), min(confidence, 1.0))

    def get_location(self, cells: List[Dict]) -> Optional[Tuple[float, float, float]]:
        if not cells or not self.known_towers:
            return None
        matched_towers: List[Dict] = []
        for cell in cells:
            tower_id = f"{cell['mcc']}-{cell['mnc']}-{cell['tac']}-{cell['ci']}"
            if tower_id in self.known_towers:
                tower = self.known_towers[tower_id]
                distance, confidence = self._estimate_distance_from_signal(
                    cell['rsrp'], cell.get('rsrq', -10))
                self.known_towers[tower_id]['last_seen'] = time.time()
                tower_confidence = tower['confidence']
                if tower.get('auto_learned', False):
                    tower_confidence *= 0.8
                matched_towers.append({
                    'lat': tower['lat'],
                    'lon': tower['lon'],
                    'distance': distance,
                    'radius': tower['radius_m'],
                    'confidence': confidence * tower_confidence,
                    'rsrp': cell['rsrp'],
                    'registered': cell.get('registered', False),
                    'tower_id': tower_id
                })
        if not matched_towers:
            return None
        registered = [t for t in matched_towers if t['registered']]
        if registered:
            if len(registered) >= 2:
                total_weight = sum(t['confidence'] for t in registered)
                if total_weight > 0:
                    lat = sum(t['lat'] * t['confidence'] for t in registered) / total_weight
                    lon = sum(t['lon'] * t['confidence'] for t in registered) / total_weight
                    avg_accuracy = sum(t['radius'] * t['confidence'] for t in registered) / total_weight
                    return (lat, lon, avg_accuracy)
            best = registered[0]
            return (best['lat'], best['lon'], best['radius'])
        if matched_towers:
            total_weight = sum(t['confidence'] for t in matched_towers)
            if total_weight > 0 and len(matched_towers) >= 2:
                lat = sum(t['lat'] * t['confidence'] for t in matched_towers) / total_weight
                lon = sum(t['lon'] * t['confidence'] for t in matched_towers) / total_weight
                avg_accuracy = sum(t['radius'] * t['confidence'] for t in matched_towers) / total_weight
                return (lat, lon, avg_accuracy)
            best = matched_towers[0]
            return (best['lat'], best['lon'], best['radius'])
        return None

    def learn_tower_automatically(self, ci: int, tac: int, mcc: int, mnc: int,
                                   lat: float, lon: float, rsrp: float,
                                   confidence: float = 0.3) -> None:
        tower_id = f"{mcc}-{mnc}-{tac}-{ci}"
        if tower_id not in self.known_towers:
            if rsrp > -80:
                radius = 200.0
            elif rsrp > -90:
                radius = 500.0
            elif rsrp > -100:
                radius = 1000.0
            else:
                radius = 2000.0
            self.known_towers[tower_id] = {
                'ci': ci, 'tac': tac, 'mcc': mcc, 'mnc': mnc,
                'lat': lat, 'lon': lon, 'radius_m': radius,
                'confidence': confidence, 'added_at': time.time(),
                'last_seen': time.time(), 'auto_learned': True,
                'first_rsrp': rsrp, 'update_count': 1
            }
            self.towers_learned = len(self.known_towers)
        else:
            tower = self.known_towers[tower_id]
            old_conf = tower['confidence']
            total_conf = old_conf + confidence
            if total_conf > 0:
                tower['lat'] = (tower['lat'] * old_conf + lat * confidence) / total_conf
                tower['lon'] = (tower['lon'] * old_conf + lon * confidence) / total_conf
                tower['confidence'] = min(0.95, old_conf + confidence * 0.1)
                tower['last_seen'] = time.time()
                tower['update_count'] = tower.get('update_count', 0) + 1
                tower['radius_m'] = max(100.0, tower['radius_m'] * 0.95)

    def get_stats(self) -> Dict[str, Any]:
        auto_learned = sum(1 for t in self.known_towers.values() if t.get('auto_learned', False))
        return {
            'known_towers': len(self.known_towers),
            'towers_learned': self.towers_learned,
            'auto_learned': auto_learned,
            'scans_performed': self.scans_performed,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_scan_error,
            'auto_learn_enabled': self.auto_learn_enabled
        }

    def cleanup_old_towers(self, max_age_hours: float = 720.0) -> int:
        now = time.time()
        max_age_sec = max_age_hours * 3600
        to_remove: List[str] = []
        for tower_id, tower in self.known_towers.items():
            if tower.get('auto_learned', False):
                last_seen = tower.get('last_seen', tower.get('added_at', 0))
                if now - last_seen > max_age_sec:
                    to_remove.append(tower_id)
        for tower_id in to_remove:
            del self.known_towers[tower_id]
        return len(to_remove)

    def get_best_tower(self) -> Optional[Dict[str, Any]]:
        if not self.last_scan_result:
            return None
        best_cell = None
        best_rsrp = -999
        for cell in self.last_scan_result:
            tower_id = f"{cell['mcc']}-{cell['mnc']}-{cell['tac']}-{cell['ci']}"
            if tower_id in self.known_towers and cell['rsrp'] > best_rsrp:
                best_rsrp = cell['rsrp']
                best_cell = cell
        if best_cell:
            tower_id = f"{best_cell['mcc']}-{best_cell['mnc']}-{best_cell['tac']}-{best_cell['ci']}"
            return {
                'tower_id': tower_id,
                'rsrp': best_cell['rsrp'],
                'location': (self.known_towers[tower_id]['lat'],
                             self.known_towers[tower_id]['lon']),
                'radius': self.known_towers[tower_id]['radius_m']
            }
        return None

# ================================================================================
# SECCION 13: GEOCERCA MEJORADA
# ================================================================================
class Geofence:
    def __init__(self, fence_id: str, center: Coordinate, radius_km: float) -> None:
        self.id = fence_id
        self.center = center
        self.radius = radius_km
        self.created_at = datetime.now(timezone.utc)
        self.last_triggered: Optional[datetime] = None
        self.trigger_count: int = 0
        self.metadata: Dict[str, Any] = {}

    def contains(self, coord: Coordinate) -> bool:
        return coord.distance_to(self.center) <= self.radius

    def get_area_km2(self) -> float:
        return math.pi * (self.radius ** 2)

    def get_perimeter_km(self) -> float:
        return 2 * math.pi * self.radius

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "center": self.center.to_dict(),
            "radius_km": self.radius,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Geofence':
        center_coord = Coordinate(
            data["center"].get("latitude", 0),
            data["center"].get("longitude", 0)
        )
        fence = cls(data["id"], center_coord, data["radius_km"])
        if "created_at" in data:
            try:
                fence.created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        if "metadata" in data:
            fence.metadata = data["metadata"]
        return fence

class GeofenceManager:
    def __init__(self) -> None:
        self.fences: Dict[str, Geofence] = {}
        self._listeners: Dict[str, List[Callable[[str, bool], None]]] = {}
        self._enter_exit_listeners: Dict[str, List[Callable[[str, bool], None]]] = {}
        self._previous_states: Dict[str, bool] = {}
        self._lock = threading.RLock()

    def add(self, fence: Geofence) -> None:
        with self._lock:
            self.fences[fence.id] = fence
            self._listeners.setdefault(fence.id, [])
            self._enter_exit_listeners.setdefault(fence.id, [])
            self._previous_states[fence.id] = False

    def remove(self, fence_id: str) -> None:
        with self._lock:
            self.fences.pop(fence_id, None)
            self._listeners.pop(fence_id, None)
            self._enter_exit_listeners.pop(fence_id, None)
            self._previous_states.pop(fence_id, None)

    def get(self, fence_id: str) -> Optional[Geofence]:
        return self.fences.get(fence_id)

    def get_all(self) -> List[Geofence]:
        return list(self.fences.values())

    def get_active_fences(self, coord: Coordinate) -> List[Geofence]:
        return [f for f in self.fences.values() if f.contains(coord)]

    def on_enter_exit(self, fence_id: str, callback: Callable[[str, bool], None]) -> None:
        self._enter_exit_listeners.setdefault(fence_id, []).append(callback)

    def update(self, coord: Coordinate) -> Dict[str, bool]:
        states: Dict[str, bool] = {}
        with self._lock:
            for fid, fence in self.fences.items():
                inside = fence.contains(coord)
                states[fid] = inside
                if inside:
                    fence.trigger_count += 1
                    fence.last_triggered = datetime.now(timezone.utc)
                prev_state = self._previous_states.get(fid, False)
                if inside != prev_state:
                    for cb in self._enter_exit_listeners.get(fid, []):
                        try:
                            cb(fid, inside)
                        except Exception:
                            pass
                    for cb in self._listeners.get(fid, []):
                        try:
                            cb(fid, inside)
                        except Exception:
                            pass
                self._previous_states[fid] = inside
        return states

    def get_state(self, fence_id: str) -> Optional[bool]:
        return self._previous_states.get(fence_id)

    def get_statistics(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            'total_fences': len(self.fences),
            'active_listeners': sum(len(v) for v in self._listeners.values()),
            'fences': {}
        }
        for fid, fence in self.fences.items():
            stats['fences'][fid] = {
                'radius_km': fence.radius,
                'area_km2': fence.get_area_km2(),
                'trigger_count': fence.trigger_count,
                'last_triggered': fence.last_triggered.isoformat() if fence.last_triggered else None,
                'currently_inside': self._previous_states.get(fid, False)
            }
        return stats

    def save(self, path: str) -> None:
        try:
            data = [f.to_dict() for f in self.fences.values()]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            count = 0
            for item in data:
                fence = Geofence.from_dict(item)
                self.add(fence)
                count += 1
        except Exception:
            pass

    def clear(self) -> None:
        with self._lock:
            self.fences.clear()
            self._listeners.clear()
            self._enter_exit_listeners.clear()
            self._previous_states.clear()

# ================================================================================
# SECCION 14: EXPORTADOR DE TRAYECTORIA
# ================================================================================
class TrajectoryExporter:
    def __init__(self) -> None:
        self.waypoints: List[Coordinate] = []
        self.max_points: int = MAX_TRAJECTORY_POINTS

    def add_waypoint(self, coord: Coordinate) -> None:
        self.waypoints.append(coord)
        if len(self.waypoints) > self.max_points:
            self.waypoints = self.waypoints[-(self.max_points // 2):]

    def clear(self) -> None:
        self.waypoints.clear()

    def to_gpx(self, filename: Optional[str] = None) -> str:
        if not filename:
            filename = "track_{}.gpx".format(time.strftime('%Y%m%d_%H%M%S'))
        gpx_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="UltraHybridGPS">',
            '  <trk>',
            '    <name>UltraHybrid Track</name>',
            '    <trkseg>'
        ]
        for wp in self.waypoints:
            gpx_lines.append(
                '      <trkpt lat="{:.8f}" lon="{:.8f}">'.format(wp.latitude, wp.longitude))
            if wp.altitude:
                gpx_lines.append('        <ele>{:.2f}</ele>'.format(wp.altitude))
            gpx_lines.append(
                '        <time>{}</time>'.format(
                    datetime.fromtimestamp(wp.timestamp).strftime("%Y-%m-%dT%H:%M:%SZ")))
            gpx_lines.append(
                '        <desc>Accuracy: {:.1f}m, Source: {}</desc>'.format(
                    wp.accuracy, wp.source))
            gpx_lines.append('      </trkpt>')
        gpx_lines.extend(['    </trkseg>', '  </trk>', '</gpx>'])
        content = '\n'.join(gpx_lines)
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception:
            pass
        return content

    def to_kml(self, filename: Optional[str] = None) -> str:
        if not filename:
            filename = "track_{}.kml".format(time.strftime('%Y%m%d_%H%M%S'))
        kml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '  <Document>',
            '    <name>UltraHybrid Track</name>',
            '    <Placemark>',
            '      <name>Route</name>',
            '      <LineString>',
            '        <coordinates>'
        ]
        coords = []
        for wp in self.waypoints:
            coords.append("{:.8f},{:.8f},{:.2f}".format(
                wp.longitude, wp.latitude, wp.altitude))
        kml_lines.append('          ' + ' '.join(coords))
        kml_lines.extend([
            '        </coordinates>',
            '      </LineString>',
            '    </Placemark>',
            '  </Document>',
            '</kml>'
        ])
        content = '\n'.join(kml_lines)
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception:
            pass
        return content

    def get_summary(self) -> Dict[str, Any]:
        if len(self.waypoints) < 2:
            return {'points': len(self.waypoints), 'distance_m': 0.0,
                    'duration_sec': 0.0, 'avg_speed_ms': 0.0}
        total_distance = 0.0
        for i in range(1, len(self.waypoints)):
            total_distance += self.waypoints[i - 1].distance_to_meters(self.waypoints[i])
        duration = self.waypoints[-1].timestamp - self.waypoints[0].timestamp
        return {
            'points': len(self.waypoints),
            'distance_m': round(total_distance, 2),
            'duration_sec': round(duration, 2),
            'avg_speed_ms': round(total_distance / duration, 2) if duration > 0 else 0.0
        }

# ================================================================================
# SECCION 15: PROVEEDORES DE GPS (REAL / SIMULADO) + RADAR WIFI
# ================================================================================
class GPSProvider:
    def get_location(self) -> Optional[Coordinate]:
        raise NotImplementedError

    def get_speed_kmh(self) -> float:
        return 0.0

class SimulatedGPS(GPSProvider):
    def __init__(self, initial: Optional[Coordinate] = None,
                 radius_km: float = 10.0, seed: Optional[int] = None) -> None:
        if seed is not None:
            random.seed(seed)
        self.current = initial or Coordinate(0.0, 0.0)
        self.radius = radius_km
        self.last_update = time.time()
        self._speed: float = 0.0

    def get_location(self) -> Coordinate:
        now = time.time()
        dt = min(1.0, now - self.last_update)
        self.last_update = now
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, self.radius * dt)
        new_lat = self.current.latitude + (dist * math.cos(angle)) / 111.0
        new_lon = self.current.longitude + (
            dist * math.sin(angle)) / (111.0 * math.cos(math.radians(self.current.latitude)))
        self.current = Coordinate(new_lat, new_lon, self.current.altitude)
        self._speed = dist / dt if dt > 0 else 0.0
        return self.current

    def get_speed_kmh(self) -> float:
        return self._speed * 3600.0

class TermuxGPS(GPSProvider):
    """Proveedor GPS real con fallback automatico GPS -> Network."""
    def __init__(self) -> None:
        self._available = self._check_termux()
        self.last_location: Optional[Coordinate] = None
        self.history: deque = deque(maxlen=100)

    def _check_termux(self) -> bool:
        if not IS_TERMUX:
            return False
        try:
            r = subprocess.run(['which', 'termux-location'],
                               capture_output=True, timeout=2)
            return r.returncode == 0
        except Exception:
            return False

    def _validar_lectura(self, lat: float, lon: float) -> bool:
        """Valida que una lectura GPS sea fisicamente posible."""
        if not (-90.0 <= lat <= 90.0):
            return False
        if not (-180.0 <= lon <= 180.0):
            return False
        if abs(lat) < 0.001 and abs(lon) < 0.001:
            return False
        return True

    def get_location(self) -> Optional[Coordinate]:
        """Obtiene ubicacion con fallback automatico GPS -> Network."""
        if not self._available:
            return None
        # Intentar primero GPS satelital (mas preciso), luego network
        for provider in ['gps', 'network']:
            try:
                timeout = 20 if provider == 'gps' else 10
                result = subprocess.run(
                    ['termux-location', '-p', provider],
                    capture_output=True, text=True, timeout=timeout
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    lat = data.get('latitude')
                    lon = data.get('longitude')
                    accuracy = data.get('accuracy', 10.0)
                    if lat is not None and lon is not None:
                        # Validar coordenadas
                        if not self._validar_lectura(float(lat), float(lon)):
                            continue
                        coord = Coordinate(float(lat), float(lon),
                                           accuracy=accuracy, source=provider)
                        self.last_location = coord
                        self.history.append(coord)
                        return coord
            except Exception:
                continue  # Probar siguiente provider
        return None

    def get_speed_kmh(self) -> float:
        if len(self.history) < 2:
            return 0.0
        d = self.history[-1].distance_to(self.history[-2])
        dt = 5.0
        speed = (d / dt) * 3600.0 if dt > 0 else 0.0
        # Limitar velocidad a 0-500 km/h (sanity check)
        return max(0.0, min(500.0, speed))

def create_gps_provider(use_real: bool = True,
                        fallback_to_sim: bool = False) -> GPSProvider:
    # Si no estamos en Termux, siempre usamos simulación
    if not IS_TERMUX:
        return SimulatedGPS()
    if use_real:
        return TermuxGPS()
    return SimulatedGPS()

def compute_wifi_radar(networks: List[Dict]) -> List[int]:
    radar = [0] * 8
    for i, net in enumerate(networks):
        rssi = net.get("rssi", -100)
        pct = max(0, min(100, int(((rssi + 100) / 70) * 100)))
        sector = i % 8
        if pct > radar[sector]:
            radar[sector] = pct
    return radar

def format_radar_compact(radar: List[int]) -> str:
    sectores = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return " ".join("{}:{:2d}%".format(s, radar[i]) for i, s in enumerate(sectores))
# ================================================================================
# SECCION 16: NUCLEO GPS MEJORADO (GPSCore Ultra)
# ================================================================================
class GPSCore:
    """Nucleo principal de GPS con fusion de sensores y aprendizaje automatico."""
    def __init__(self, provider: Optional[GPSProvider] = None,
                 use_kalman: bool = True) -> None:
        self.provider = provider or create_gps_provider(use_real=False, fallback_to_sim=True)
        self.geofence = GeofenceManager()
        self.use_kalman = use_kalman
        if use_kalman:
            self.kalman: Optional[ExtendedKalmanFilter] = ExtendedKalmanFilter()
        else:
            self.kalman = None
        self._last_coord: Optional[Coordinate] = None
        self._running: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._interval: float = 1.0
        self._listeners: List[Callable[[Coordinate], None]] = []
        self.dgps = DifferentialCorrector()
        self.imu = IMUFusion()
        self.bluetooth = AdvancedBluetoothScanner()
        self.bluetooth.enable_auto_learning(True)
        self.wifi = WiFiPositioning()
        self.cellular = CellularPositioning()
        self.cellular.auto_learn_enabled = True
        self.exporter = TrajectoryExporter()
        self.position_history: deque = deque(maxlen=MAX_POSITION_HISTORY)
        self.accuracy_history: deque = deque(maxlen=MAX_ACCURACY_HISTORY)
        self.consecutive_failures: int = 0
        self.last_gps_quality_location: Optional[Tuple[float, float, float, float]] = None
        self.last_update_time: Optional[float] = None
        self.anti_jump_enabled: bool = True
        self.smoothing_enabled: bool = True
        self.source_weights: Dict[str, float] = {
            'gps': 0.55,
            'bluetooth': 0.20,
            'wifi': 0.10,
            'cellular': 0.15
        }
        self.stats: Dict[str, Any] = {
            'gps_updates': 0,
            'bt_updates': 0,
            'wifi_updates': 0,
            'cellular_updates': 0,
            'fused_updates': 0,
            'total_distance_m': 0.0,
            'beacons_learned': 0,
            'towers_learned': 0,
            'wifi_learned': 0
        }
        self.last_wifi_networks: List[Dict] = []
        self._uber_bridge = None  # Inicializado explicitamente
        self._setup_default_dgps()

    def _validar_lectura_gps(self, lat: float, lon: float, speed_kmh: float = 0.0) -> bool:
        """Valida que una lectura GPS sea fisicamente posible."""
        if not (-90.0 <= lat <= 90.0):
            return False
        if not (-180.0 <= lon <= 180.0):
            return False
        if abs(speed_kmh) > 500.0:
            return False
        if abs(lat) < 0.001 and abs(lon) < 0.001:
            return False
        return True

    def _setup_default_dgps(self) -> None:
        reference_stations = [
            (8.985, -79.52, "Albrook", 1.0),
            (8.88, -79.76, "Arraijan", 1.0),
            (8.875, -79.78, "Chorrera", 1.0),
            (8.89, -79.80, "San Carlos", 0.8),
            (8.85, -79.82, "Veracruz", 0.8),
        ]
        for lat, lon, name, weight in reference_stations:
            self.dgps.add_reference_station((lat, lon), name, weight)

    def start(self, interval_seconds: float = 1.0) -> None:
        if self._running:
            return
        self._interval = interval_seconds
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _calculate_dt(self) -> float:
        now = time.time()
        if self.last_update_time is None:
            self.last_update_time = now
            return 0.5
        dt = now - self.last_update_time
        self.last_update_time = now
        return MathUtils.clamp(dt, 0.01, 5.0)

    def _is_gps_quality_valid(self) -> bool:
        if self.last_gps_quality_location is None:
            return False
        _, _, _, timestamp = self.last_gps_quality_location
        return (time.time() - timestamp) < GPS_QUALITY_AGE_SECONDS

    def _force_bluetooth_learning(self) -> int:
        if not self._is_gps_quality_valid():
            return 0
        gps_lat, gps_lon, gps_acc, _ = self.last_gps_quality_location
        bt_devices = self.bluetooth.scan_advanced()
        learned = 0
        for device in bt_devices:
            mac = device['mac']
            if mac not in self.bluetooth.known_beacons and device['distance'] < 20.0:
                confidence = 0.7 * (1.0 - min(device['distance'] / 20.0, 0.9))
                self.bluetooth.learn_beacon_automatically(mac, gps_lat, gps_lon, confidence)
                learned += 1
        if learned > 0:
            self.stats['beacons_learned'] += learned
        return learned

    def _force_cellular_learning(self) -> int:
        if not self._is_gps_quality_valid():
            return 0
        gps_lat, gps_lon, gps_acc, _ = self.last_gps_quality_location
        cells = self.cellular.scan()
        learned = 0
        for cell in cells:
            tower_id = f"{cell['mcc']}-{cell['mnc']}-{cell['tac']}-{cell['ci']}"
            if tower_id not in self.cellular.known_towers:
                confidence = 0.3 * (1.0 - min(cell.get('rsrp', -100) / -50, 0.8))
                self.cellular.learn_tower_automatically(
                    cell['ci'], cell['tac'], cell['mcc'], cell['mnc'],
                    gps_lat, gps_lon, cell.get('rsrp', -100), confidence
                )
                learned += 1
        if learned > 0:
            self.stats['towers_learned'] += learned
        return learned

    def _force_wifi_learning(self) -> int:
        if not self._is_gps_quality_valid():
            return 0
        gps_lat, gps_lon, gps_acc, _ = self.last_gps_quality_location
        wifi_nets = self.wifi.scan()
        learned = 0
        for net in wifi_nets:
            bssid = net.get('bssid', '').upper().strip()
            if bssid and bssid not in self.wifi.known_networks:
                self.wifi.add_network(
                    bssid, gps_lat, gps_lon,
                    net.get('ssid', 'auto_learned'),
                    net.get('rssi', -40)
                )
                learned += 1
        if learned > 0:
            self.stats['wifi_learned'] += learned
        return learned

    def _force_all_learning(self) -> Dict[str, int]:
        return {
            'bluetooth': self._force_bluetooth_learning(),
            'cellular': self._force_cellular_learning(),
            'wifi': self._force_wifi_learning()
        }

    def _update_loop(self) -> None:
        learning_counter = 0
        learning_interval = 30
        while not self._stop_event.is_set():
            dt = self._calculate_dt()
            if self.kalman:
                self.kalman.set_dt(dt)
                self.kalman.predict()
            raw_gps = self.provider.get_location()
            gps_valid = False
            gps_loc = None
            if raw_gps and raw_gps.is_valid():
                # Sanity check: validar coordenadas
                if not self._validar_lectura_gps(raw_gps.latitude, raw_gps.longitude):
                    gps_valid = False
                else:
                    age = time.time() - raw_gps.timestamp
                    if age < 10.0 and raw_gps.accuracy <= 50.0:
                        self.stats['gps_updates'] += 1
                        gps_valid = True
                        if self.kalman:
                            kalman_pos = self.kalman.update(
                                raw_gps.latitude, raw_gps.longitude, raw_gps.accuracy)
                            lat, lon, accuracy = self.dgps.correct(
                                kalman_pos[0], kalman_pos[1], raw_gps.accuracy)
                        else:
                            lat, lon, accuracy = self.dgps.correct(
                                raw_gps.latitude, raw_gps.longitude, raw_gps.accuracy)
                        imu_pred_lat, imu_pred_lon = self.imu.predict(lat, lon, dt)
                        lat, lon = self.imu.update(lat, lon, imu_pred_lat, imu_pred_lon)
                        gps_loc = Coordinate(lat, lon, raw_gps.altitude,
                                             accuracy, 'gps_enhanced')
                        if accuracy < 10.0 and (self.kalman is None or self.kalman.get_quality() > 0.5):
                            self.last_gps_quality_location = (lat, lon, accuracy, time.time())
            locations: List[Tuple[Coordinate, float]] = (
                [(gps_loc, self.source_weights['gps'])] if gps_valid else []
            )
            try:
                bt_devices = self.bluetooth.scan_advanced()
                bt_pos = self.bluetooth.get_best_location(bt_devices) if bt_devices else None
                if bt_pos:
                    bt_loc = Coordinate(bt_pos[0], bt_pos[1],
                                        accuracy=bt_pos[2], source='bluetooth')
                    locations.append((bt_loc, self.source_weights['bluetooth']))
                    self.stats['bt_updates'] += 1
            except Exception:
                pass
            try:
                wifi_nets = self.wifi.scan()
                self.last_wifi_networks = wifi_nets
                wifi_pos = self.wifi.get_location(wifi_nets)
                if wifi_pos:
                    wifi_loc = Coordinate(wifi_pos[0], wifi_pos[1],
                                          accuracy=wifi_pos[2], source='wifi')
                    locations.append((wifi_loc, self.source_weights['wifi']))
                    self.stats['wifi_updates'] += 1
            except Exception:
                pass
            try:
                cell_cells = self.cellular.scan()
                cell_pos = self.cellular.get_location(cell_cells) if cell_cells else None
                if cell_pos:
                    cell_loc = Coordinate(cell_pos[0], cell_pos[1],
                                          accuracy=cell_pos[2], source='cellular')
                    locations.append((cell_loc, self.source_weights['cellular']))
                    self.stats['cellular_updates'] += 1
            except Exception:
                pass
            learning_counter += 1
            if learning_counter >= learning_interval and self._is_gps_quality_valid():
                if self._last_coord:
                    self._force_all_learning()
                learning_counter = 0
            if not locations:
                self.consecutive_failures += 1
                if self._last_coord and self.consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                    pred_dt = min(1.0, self.consecutive_failures * 0.5)
                    pred_lat, pred_lon = self.imu.predict(
                        self._last_coord.latitude, self._last_coord.longitude, pred_dt)
                    predicted = Coordinate(
                        pred_lat, pred_lon,
                        accuracy=self._last_coord.accuracy + self.consecutive_failures * 3.0,
                        source='predicted')
                    self._last_coord = predicted
                    self.exporter.add_waypoint(predicted)
            else:
                self.consecutive_failures = 0
                total_weight = sum(w for _, w in locations)
                if total_weight > 0:
                    fused_lat = sum(loc.latitude * w for loc, w in locations) / total_weight
                    fused_lon = sum(loc.longitude * w for loc, w in locations) / total_weight
                    fused_accuracy = sum(loc.accuracy * w for loc, w in locations) / total_weight
                    result = Coordinate(fused_lat, fused_lon,
                                        accuracy=fused_accuracy, source='hybrid')
                    if self._last_coord:
                        self.stats['total_distance_m'] += self._last_coord.distance_to_meters(result)
                    self._last_coord = result
                    self.exporter.add_waypoint(result)
                    self.geofence.update(result)
                    for cb in self._listeners:
                        try:
                            cb(result)
                        except Exception:
                            pass
            time.sleep(self._interval)

    def get_location(self) -> Optional[Coordinate]:
        return self._last_coord

    def get_speed(self) -> float:
        if self._last_coord and len(self.exporter.waypoints) >= 2:
            last_two = self.exporter.waypoints[-2:]
            return last_two[-1].distance_to(last_two[-2]) * 3600.0 / max(
                0.1, last_two[-1].timestamp - last_two[-2].timestamp)
        return 0.0

    def get_learning_stats(self) -> Dict[str, Any]:
        return {
            'bluetooth': {
                'known_beacons': len(self.bluetooth.known_beacons),
                'auto_learn_enabled': self.bluetooth.auto_learn_enabled,
                'fingerprints': len(self.bluetooth.fingerprint_db),
                'beacons_learned': self.stats.get('beacons_learned', 0)
            },
            'cellular': {
                'known_towers': len(self.cellular.known_towers),
                'auto_learn_enabled': self.cellular.auto_learn_enabled,
                'towers_learned': self.cellular.towers_learned
            },
            'wifi': {
                'known_networks': len(self.wifi.known_networks),
                'wifi_learned': self.stats.get('wifi_learned', 0)
            },
            'dgps': {
                'stations': len(self.dgps.reference_stations),
                'is_calibrated': self.dgps.is_calibrated,
                'corrections_applied': self.dgps.stats.get('corrections_applied', 0)
            },
            'gps_quality_valid': self._is_gps_quality_valid(),
            'consecutive_failures': self.consecutive_failures
        }

    def on_location_change(self, callback: Callable[[Coordinate], None]) -> None:
        self._listeners.append(callback)

    def add_geofence(self, fence: Geofence) -> None:
        self.geofence.add(fence)

    def get_stats(self) -> Dict[str, Any]:
        return {
            'gps_updates': self.stats['gps_updates'],
            'bt_updates': self.stats['bt_updates'],
            'wifi_updates': self.stats['wifi_updates'],
            'cellular_updates': self.stats['cellular_updates'],
            'fused_updates': self.stats['fused_updates'],
            'total_distance_m': round(self.stats['total_distance_m'], 2),
            'kalman_quality': self.kalman.get_quality() if self.kalman else 1.0,
            'dgps_stats': self.dgps.get_stats(),
            'beacons_known': len(self.bluetooth.known_beacons),
            'wifi_networks_known': len(self.wifi.known_networks),
            'cell_towers_known': self.cellular.towers_learned,
            'trajectory_points': len(self.exporter.waypoints),
            'beacons_learned': self.stats.get('beacons_learned', 0),
            'wifi_learned': self.stats.get('wifi_learned', 0),
            'towers_learned': self.stats.get('towers_learned', 0)
        }

    def force_learning(self) -> Dict[str, int]:
        return self._force_all_learning()

    def get_diagnostics(self) -> Dict[str, Any]:
        diag = {
            'running': self._running,
            'interval': self._interval,
            'last_coord': self._last_coord.to_dict() if self._last_coord else None,
            'gps_quality_valid': self._is_gps_quality_valid(),
            'consecutive_failures': self.consecutive_failures,
            'source_weights': self.source_weights.copy(),
            'stats': self.stats.copy(),
            'learning_stats': self.get_learning_stats()
        }
        if self.kalman:
            diag['kalman_diagnostics'] = self.kalman.get_diagnostics()
        return diag

# ================================================================================
# SECCION 17: ENRUTAMIENTO (Grafos, Dijkstra, A*)
# ================================================================================
@dataclass
class Node:
    id: str
    lat: float
    lon: float
    name: str = ""

@dataclass
class Edge:
    id: str
    from_node: str
    to_node: str
    distance_km: float
    base_time_min: float
    road_type: str = "local"
    toll_cost: float = 0.0
    traffic_multiplier: float = 1.0

class RouteGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.adj: Dict[str, List[str]] = defaultdict(list)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge, bidirectional: bool = True) -> None:
        self.edges[edge.id] = edge
        self.adj[edge.from_node].append(edge.id)
        if bidirectional:
            rev_id = "{}_rev".format(edge.id)
            rev = Edge(rev_id, edge.to_node, edge.from_node,
                       edge.distance_km, edge.base_time_min,
                       edge.road_type, edge.toll_cost, edge.traffic_multiplier)
            self.edges[rev_id] = rev
            self.adj[edge.to_node].append(rev_id)

    def get_edges_from(self, node_id: str) -> List[Edge]:
        return [self.edges[eid] for eid in self.adj.get(node_id, []) if eid in self.edges]

class RoutingEngine:
    def __init__(self, graph: RouteGraph, traffic_enabled: bool = False) -> None:
        self.graph = graph
        self.traffic_enabled = traffic_enabled

    def _edge_cost(self, edge: Edge, objective: str = "time") -> float:
        mult = edge.traffic_multiplier if self.traffic_enabled else 1.0
        if objective == "time":
            return edge.base_time_min * mult
        else:
            return edge.distance_km

    def shortest_path(self, from_id: str, to_id: str, objective: str = "time",
                      algorithm: str = "a_star") -> Tuple[List[str], List[str], float]:
        if algorithm == "dijkstra":
            return self._dijkstra(from_id, to_id, objective)
        else:
            return self._a_star(from_id, to_id, objective)

    def _dijkstra(self, src: str, dst: str, objective: str) -> Tuple[List[str], List[str], float]:
        if src not in self.graph.nodes or dst not in self.graph.nodes:
            return [], [], float('inf')
        dist = {src: 0.0}
        prev_node = {}
        prev_edge = {}
        pq = [(0.0, src)]
        visited = set()
        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if u == dst:
                break
            for e in self.graph.get_edges_from(u):
                v = e.to_node
                w = self._edge_cost(e, objective)
                nd = d + w
                if v not in dist or nd < dist[v]:
                    dist[v] = nd
                    prev_node[v] = u
                    prev_edge[v] = e.id
                    heapq.heappush(pq, (nd, v))
        if dst not in prev_node and src != dst:
            return [], [], float('inf')
        path_nodes, path_edges = [], []
        cur = dst
        while cur != src:
            path_nodes.append(cur)
            eid = prev_edge.get(cur)
            if eid is None:
                break
            path_edges.append(eid)
            cur = prev_node.get(cur)
            if cur is None:
                break
        path_nodes.append(src)
        path_nodes.reverse()
        path_edges.reverse()
        return path_nodes, path_edges, dist.get(dst, float('inf'))

    def _heuristic(self, node_id: str, target_lat: float, target_lon: float) -> float:
        n = self.graph.nodes.get(node_id)
        if not n:
            return 0.0
        return haversine(n.lat, n.lon, target_lat, target_lon)

    def _a_star(self, src: str, dst: str, objective: str) -> Tuple[List[str], List[str], float]:
        if src not in self.graph.nodes or dst not in self.graph.nodes:
            return [], [], float('inf')
        target = self.graph.nodes[dst]
        open_set = [(0.0, src)]
        g_score = {src: 0.0}
        f_score = {src: self._heuristic(src, target.lat, target.lon)}
        came_from = {}
        visited = set()
        while open_set:
            _, cur = heapq.heappop(open_set)
            if cur == dst:
                break
            if cur in visited:
                continue
            visited.add(cur)
            for e in self.graph.get_edges_from(cur):
                nxt = e.to_node
                if nxt in visited:
                    continue
                tentative_g = g_score[cur] + self._edge_cost(e, objective)
                if nxt not in g_score or tentative_g < g_score[nxt]:
                    came_from[nxt] = (cur, e.id)
                    g_score[nxt] = tentative_g
                    f = tentative_g + self._heuristic(nxt, target.lat, target.lon)
                    f_score[nxt] = f
                    heapq.heappush(open_set, (f, nxt))
        if dst not in came_from and src != dst:
            return [], [], float('inf')
        path_nodes, path_edges = [], []
        cur = dst
        while cur != src:
            path_nodes.append(cur)
            _, eid = came_from.get(cur, (None, None))
            if eid is None:
                break
            path_edges.append(eid)
            cur, _ = came_from.get(cur, (None, None))
            if cur is None:
                break
        path_nodes.append(src)
        path_nodes.reverse()
        path_edges.reverse()
        return path_nodes, path_edges, g_score.get(dst, float('inf'))

# ================================================================================
# SECCION 18: MATCHING (Hungarian, Gale-Shapley, Top-K, GeoMatcher)
# ================================================================================
class SimilarityMetrics:
    @staticmethod
    def cosine(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        na = math.sqrt(sum(a * a for a in vec_a))
        nb = math.sqrt(sum(b * b for b in vec_b))
        if na == 0 or nb == 0:
            return 0.0
        return (dot / (na * nb) + 1) / 2

    @staticmethod
    def euclidean(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b:
            return 1.0
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))
        maxd = math.sqrt(len(vec_a))
        return min(1.0, d / maxd) if maxd > 0 else 0.0

    @staticmethod
    def jaccard(set_a: Set, set_b: Set) -> float:
        if not set_a and not set_b:
            return 1.0
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union > 0 else 0.0

    @staticmethod
    def weighted(feats_a: Dict, feats_b: Dict, weights: Dict) -> float:
        total_w = 0.0
        wsum = 0.0
        for f, w in weights.items():
            if f in feats_a and f in feats_b:
                diff = abs(feats_a[f] - feats_b[f])
                sim = 1.0 - min(1.0, diff)
                wsum += w * sim
                total_w += w
        return wsum / total_w if total_w > 0 else 0.0

    @staticmethod
    def geographic(coord_a: Optional[Tuple], coord_b: Optional[Tuple],
                   max_km: float = 100.0) -> float:
        if coord_a is None or coord_b is None:
            return 0.5
        dist = haversine(coord_a[0], coord_a[1], coord_b[0], coord_b[1])
        return max(0.0, 1.0 - (dist / max_km))

class TopKCandidates:
    def __init__(self, k: int = 10) -> None:
        self.k = k

    def find(self, query: Dict[str, float],
             candidates: List[Tuple[str, Dict[str, float]]],
             weights: Optional[Dict[str, float]] = None) -> List[Tuple[str, float]]:
        if weights is None:
            weights = {k: 1.0 for k in query}
        heap = []
        for cid, feats in candidates:
            score = self._score(query, feats, weights)
            if len(heap) < self.k:
                heapq.heappush(heap, (-score, cid))
            elif score > -heap[0][0]:
                heapq.heappushpop(heap, (-score, cid))
        res = [(cid, -s) for s, cid in heap]
        res.sort(key=lambda x: x[1], reverse=True)
        return res

    def _score(self, q: Dict, f: Dict, w: Dict) -> float:
        total = 0.0
        wsum = 0.0
        for key, qv in q.items():
            if key in f:
                weight = w.get(key, 1.0)
                sim = 1.0 - min(1.0, abs(qv - f[key]))
                total += weight * sim
                wsum += weight
        return total / wsum if wsum > 0 else 0.0

class HungarianAlgorithm:
    def solve(self, similarity_matrix: List[List[float]],
              maximize: bool = True) -> Tuple[List[Tuple[int, int]], float]:
        if not similarity_matrix or not similarity_matrix[0]:
            return [], 0.0
        n, m = len(similarity_matrix), len(similarity_matrix[0])
        if maximize:
            max_val = max(max(row) for row in similarity_matrix)
            cost = [[max_val - v for v in row] for row in similarity_matrix]
        else:
            cost = [row[:] for row in similarity_matrix]
        size = max(n, m)
        for i in range(size):
            if i < len(cost):
                while len(cost[i]) < size:
                    cost[i].append(float('inf'))
            else:
                cost.append([float('inf')] * size)
        u = [0.0] * (size + 1)
        v = [0.0] * (size + 1)
        p = [0] * (size + 1)
        way = [0] * (size + 1)
        for i in range(1, size + 1):
            p[0] = i
            j0 = 0
            minv = [float('inf')] * (size + 1)
            used = [False] * (size + 1)
            while True:
                used[j0] = True
                i0 = p[j0]
                delta = float('inf')
                j1 = 0
                for j in range(1, size + 1):
                    if not used[j]:
                        cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                        if cur < minv[j]:
                            minv[j] = cur
                            way[j] = j0
                for j in range(size + 1):
                    if used[j]:
                        u[p[j]] += delta
                        v[j] -= delta
                    else:
                        minv[j] -= delta
                if minv[j0] < delta:
                    delta = minv[j0]
                    j1 = j0
                if p[j0] == 0:
                    break
                while True:
                    j1 = way[j0]
                    p[j0] = p[j1]
                    j0 = j1
                    if j0 == 0:
                        break
        assignment = [p[j] - 1 for j in range(1, size + 1)]
        matches = [(i, assignment[i]) for i in range(n) if assignment[i] < m]
        total = sum(similarity_matrix[i][j] for i, j in matches)
        return matches, total if maximize else -total

class GaleShapley:
    def solve(self, men: List[str], women: List[str],
              men_prefs: Dict[str, List[str]],
              women_prefs: Dict[str, List[str]]) -> Dict[str, str]:
        women_rank = {w: {m: r for r, m in enumerate(prefs)}
                      for w, prefs in women_prefs.items()}
        engaged_w = {w: None for w in women}
        engaged_m = {m: None for m in men}
        free_men = deque(men)
        next_prop = {m: 0 for m in men}
        while free_men:
            m = free_men.popleft()
            if next_prop[m] >= len(men_prefs[m]):
                continue
            w = men_prefs[m][next_prop[m]]
            next_prop[m] += 1
            if engaged_w[w] is None:
                engaged_w[w] = m
                engaged_m[m] = w
            else:
                cur = engaged_w[w]
                if women_rank[w][m] < women_rank[w][cur]:
                    engaged_w[w] = m
                    engaged_m[m] = w
                    engaged_m[cur] = None
                    free_men.append(cur)
                else:
                    free_men.append(m)
        return {m: w for m, w in engaged_m.items() if w is not None}

class GeoMatcher:
    def __init__(self, cell_size_km: float = 10.0) -> None:
        self.cell_deg = cell_size_km / 111.0

    def _cell(self, lat: float, lon: float) -> Tuple[int, int]:
        return (int(lat / self.cell_deg), int(lon / self.cell_deg))

    def cluster(self, agents: List[Tuple[str, float, float]]) -> Dict[Tuple[int, int], List[str]]:
        clusters = defaultdict(list)
        for aid, lat, lon in agents:
            clusters[self._cell(lat, lon)].append(aid)
        return clusters

    def nearby(self, lat: float, lon: float,
               all_agents: Dict[str, Tuple[float, float]],
               radius_km: float = 20.0) -> List[Tuple[str, float]]:
        res = []
        for aid, (alat, alon) in all_agents.items():
            d = haversine(lat, lon, alat, alon)
            if d <= radius_km:
                res.append((aid, d))
        res.sort(key=lambda x: x[1])
        return res

class MatchingEngine:
    def __init__(self) -> None:
        self.hungarian = HungarianAlgorithm()
        self.gale = GaleShapley()
        self.topk = TopKCandidates()
        self.geo = GeoMatcher()
        self.agent_features: Dict[str, Dict[str, float]] = {}

    def compute_similarity(self, agent_a: Dict, agent_b: Dict,
                           weights: Optional[Dict] = None) -> Tuple[float, Dict]:
        if weights is None:
            weights = {"pref": 0.4, "rating": 0.3, "loc": 0.3}
        breakdown = {}
        if agent_a.get("preferences") and agent_b.get("preferences"):
            breakdown["pref"] = SimilarityMetrics.weighted(
                agent_a["preferences"], agent_b["preferences"],
                {k: 1.0 for k in agent_a["preferences"]}
            )
        breakdown["rating"] = 1.0 - abs(
            agent_a.get("rating", 0.5) - agent_b.get("rating", 0.5))
        if agent_a.get("location") and agent_b.get("location"):
            breakdown["loc"] = SimilarityMetrics.geographic(
                agent_a["location"], agent_b["location"], max_km=50.0)
        total = sum(weights.get(k, 0) * v for k, v in breakdown.items())
        return total, breakdown

    def update_features(self, agent_id: str, features: Dict) -> None:
        self.agent_features[agent_id] = features

    def get_recommendations(self, agent_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if agent_id not in self.agent_features:
            return []
        query = self.agent_features[agent_id]
        candidates = [(aid, f) for aid, f in self.agent_features.items()
                      if aid != agent_id]
        return self.topk.find(query, candidates)

# ================================================================================
# SECCION 19: MONITOR DE RED
# ================================================================================
class NetworkMonitor:
    def __init__(self) -> None:
        self.registry = SharedDataRegistry()
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.servers = ["8.8.8.8", "1.1.1.1", "google.com"]
        self.status = {"connected": False, "latency_ms": None, "last_check": None}

    def start(self, interval: float = 5.0) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, args=(interval,))
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self, interval: float) -> None:
        while not self._stop_event.is_set():
            self._check()
            time.sleep(interval)

    def _check(self) -> None:
        best = None
        best_lat = float('inf')
        for server in self.servers:
            lat = self._ping(server)
            if lat is not None and lat < best_lat:
                best_lat = lat
                best = server
        if best:
            self.status = {"connected": True, "latency_ms": best_lat,
                           "server": best, "last_check": time.time()}
        else:
            self.status = {"connected": False, "latency_ms": None,
                           "last_check": time.time()}
        self.registry.set("network:status", self.status)

    def _ping(self, host: str) -> Optional[float]:
        try:
            ping_cmd = 'ping'
            param = '-n' if os.name == 'nt' else '-c'
            timeout = 2
            start = time.time()
            subprocess.run([ping_cmd, param, '1', host],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout)
            return (time.time() - start) * 1000
        except Exception:
            return None

# ================================================================================
# SECCION 20: APRENDIZAJE POR REFUERZO (Ensemble)
# ================================================================================
@dataclass
class Experience:
    state: Any
    action: int
    reward: float
    next_state: Any
    done: bool
    priority: float = 1.0

class DoubleDQN:
    def __init__(self, state_dim: int, action_dim: int, lr: float = 0.001,
                 gamma: float = 0.99, epsilon: float = 1.0,
                 epsilon_end: float = 0.01, epsilon_decay: float = 0.995,
                 memory_size: int = 10000, batch_size: int = 32,
                 target_update: int = 100) -> None:
        self.s_dim = state_dim
        self.a_dim = action_dim
        self.lr = lr
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch = batch_size
        self.target_update_freq = target_update
        self.steps = 0
        self.training_steps = 0
        if HAS_NUMPY:
            self.q_net = self._init_net()
            self.target_net = self._init_net()
        else:
            self.q_table = defaultdict(lambda: [0.0] * action_dim)
        self.memory = deque(maxlen=memory_size)
        self.priorities = deque(maxlen=memory_size)
        self.alpha = 0.6
        self.beta = 0.4
        self.beta_inc = 0.001

    def _init_net(self) -> Dict:
        return {
            'w1': np.random.randn(self.s_dim, 128) * np.sqrt(2 / self.s_dim),
            'b1': np.zeros(128),
            'w2': np.random.randn(128, 64) * np.sqrt(2 / 128),
            'b2': np.zeros(64),
            'w3': np.random.randn(64, 32) * np.sqrt(2 / 64),
            'b3': np.zeros(32),
            'w4': np.random.randn(32, self.a_dim) * np.sqrt(2 / 32),
            'b4': np.zeros(self.a_dim)
        }

    def _forward(self, net: Dict, x: List) -> Any:
        x = np.array(x).flatten()
        z1 = np.dot(x, net['w1']) + net['b1']
        a1 = np.maximum(0.1 * z1, z1)
        z2 = np.dot(a1, net['w2']) + net['b2']
        a2 = np.maximum(0.1 * z2, z2)
        z3 = np.dot(a2, net['w3']) + net['b3']
        a3 = np.maximum(0.1 * z3, z3)
        return np.dot(a3, net['w4']) + net['b4']

    def select_action(self, state: Any, exploit_only: bool = False) -> int:
        if not exploit_only and random.random() < self.epsilon:
            return random.randint(0, self.a_dim - 1)
        if HAS_NUMPY:
            q = self._forward(self.q_net, state)
            return int(np.argmax(q))
        else:
            key = tuple(state) if isinstance(state, (list, tuple)) else state
            q = self.q_table.get(key, [0.0] * self.a_dim)
            return q.index(max(q))

    def store(self, state: Any, action: int, reward: float,
              next_state: Any, done: bool) -> None:
        exp = Experience(state, action, reward, next_state, done)
        self.memory.append(exp)
        priority = (abs(reward) + 0.01) ** self.alpha
        self.priorities.append(priority)

    def sample(self) -> Tuple[Optional[List], Optional[Any], Optional[Any]]:
        if len(self.memory) < self.batch:
            return None, None, None
        if HAS_NUMPY:
            probs = np.array(self.priorities) ** self.alpha
            probs /= probs.sum()
            idx = np.random.choice(len(self.memory), self.batch, p=probs, replace=False)
            weights = (len(self.memory) * probs[idx]) ** (-self.beta)
            weights /= weights.max()
            self.beta = min(1.0, self.beta + self.beta_inc)
            return [self.memory[i] for i in idx], idx, weights
        else:
            return random.sample(self.memory, self.batch), None, None

    def learn(self) -> Dict:
        batch, indices, weights = self.sample()
        if not batch:
            return {}
        loss = 0.0
        if HAS_NUMPY:
            states, targets, td_errors = [], [], []
            for exp in batch:
                q_curr = self._forward(self.q_net, exp.state)
                q_next_online = self._forward(self.q_net, exp.next_state)
                q_next_target = self._forward(self.target_net, exp.next_state)
                best_a = int(np.argmax(q_next_online))
                target = exp.reward + self.gamma * q_next_target[best_a] * (1 - exp.done)
                td = target - q_curr[exp.action]
                target_q = q_curr.copy()
                target_q[exp.action] = target
                states.append(exp.state)
                targets.append(target_q)
                td_errors.append(abs(td))
            if indices is not None:
                for idx, td in zip(indices, td_errors):
                    self.priorities[idx] = (td + 0.01) ** self.alpha
        else:
            for exp in batch:
                key = tuple(exp.state) if isinstance(exp.state, (list, tuple)) else exp.state
                nkey = tuple(exp.next_state) if isinstance(exp.next_state, (list, tuple)) else exp.next_state
                q = list(self.q_table.get(key, [0.0] * self.a_dim))
                nq = list(self.q_table.get(nkey, [0.0] * self.a_dim))
                best_a = nq.index(max(nq)) if nq else 0
                target = exp.reward + self.gamma * nq[best_a] * (1 - exp.done)
                q[exp.action] += self.lr * (target - q[exp.action])
                self.q_table[key] = q
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        self.steps += 1
        if self.steps % self.target_update_freq == 0 and HAS_NUMPY:
            for k in self.q_net:
                self.target_net[k] = self.q_net[k].copy()
        self.training_steps += 1
        return {'loss': loss, 'epsilon': self.epsilon}

    def get_epsilon(self) -> float:
        return self.epsilon

class SARSAAgent:
    def __init__(self, state_dim: int, action_dim: int, lr: float = 0.1,
                 gamma: float = 0.99, epsilon: float = 1.0,
                 epsilon_decay: float = 0.995, epsilon_end: float = 0.01) -> None:
        self.s_dim = state_dim
        self.a_dim = action_dim
        self.lr = lr
        self.gamma = gamma
        self.epsilon = epsilon
        self.eps_decay = epsilon_decay
        self.eps_end = epsilon_end
        self.q_table = defaultdict(lambda: [0.0] * action_dim)

    def select_action(self, state: Any, exploit_only: bool = False) -> int:
        if not exploit_only and random.random() < self.epsilon:
            return random.randint(0, self.a_dim - 1)
        key = tuple(state) if isinstance(state, (list, tuple)) else state
        q = self.q_table[key]
        return q.index(max(q))

    def update(self, state: Any, action: int, reward: float,
               next_state: Any, next_action: int, done: bool) -> None:
        key = tuple(state) if isinstance(state, (list, tuple)) else state
        nkey = tuple(next_state) if isinstance(next_state, (list, tuple)) else next_state
        q = list(self.q_table[key])
        nq = list(self.q_table[nkey])
        if done:
            q[action] += self.lr * (reward - q[action])
        else:
            q[action] += self.lr * (reward + self.gamma * nq[next_action] - q[action])
        self.q_table[key] = q
        self.epsilon = max(self.eps_end, self.epsilon * self.eps_decay)

class ActorCritic:
    def __init__(self, state_dim: int, action_dim: int, actor_lr: float = 0.0003,
                 critic_lr: float = 0.001, gamma: float = 0.99,
                 entropy_coef: float = 0.01) -> None:
        self.s_dim = state_dim
        self.a_dim = action_dim
        self.actor_lr = actor_lr
        self.critic_lr = critic_lr
        self.gamma = gamma
        self.entropy_coef = entropy_coef
        self.buffer = []
        if HAS_NUMPY:
            self.actor_w = np.random.randn(state_dim, action_dim) * 0.01
            self.actor_b = np.zeros(action_dim)
            self.critic_w1 = np.random.randn(state_dim, 64) * np.sqrt(2.0 / max(state_dim, 1))
            self.critic_b1 = np.zeros(64)
            self.critic_w2 = np.random.randn(64, 1) * np.sqrt(2.0 / 64)
            self.critic_b2 = np.zeros(1)
        else:
            self.actor_table = defaultdict(lambda: [1.0 / action_dim] * action_dim)
            self.critic_table = defaultdict(float)

    def _actor_probs(self, state: Any) -> Any:
        if HAS_NUMPY:
            x = np.array(state).flatten()
            logits = np.dot(x, self.actor_w) + self.actor_b
            logits = np.clip(logits, -50, 50)
            exps = np.exp(logits - np.max(logits))
            s = exps.sum()
            if s < 1e-10:
                return np.ones(self.a_dim) / self.a_dim
            return exps / s
        else:
            key = tuple(state) if isinstance(state, (list, tuple)) else state
            return self.actor_table.get(key, [1.0 / self.a_dim] * self.a_dim)

    def _critic_value(self, state: Any) -> float:
        if HAS_NUMPY:
            x = np.array(state).flatten()
            h = np.maximum(0, np.dot(x, self.critic_w1) + self.critic_b1)
            h = np.clip(h, 0, 100)
            result = np.dot(h, self.critic_w2) + self.critic_b2
            return float(result.flatten()[0]) if result.size > 0 else 0.0
        else:
            key = tuple(state) if isinstance(state, (list, tuple)) else state
            return self.critic_table.get(key, 0.0)

    def select_action(self, state: Any) -> Tuple[int, float, float]:
        probs = self._actor_probs(state)
        if HAS_NUMPY:
            probs = np.clip(probs, 0, None)
            s = probs.sum()
            if s > 0:
                probs = probs / s
            else:
                probs = np.ones(self.a_dim) / self.a_dim
            action = np.random.choice(self.a_dim, p=probs)
            log_prob = math.log(max(probs[action], 1e-8))
        else:
            r = random.random()
            cum = 0.0
            action = 0
            for i, p in enumerate(probs):
                cum += p
                if r <= cum:
                    action = i
                    break
            log_prob = math.log(max(probs[action], 1e-8))
        value = self._critic_value(state)
        return int(action), log_prob, value

    def store(self, state: Any, action: int, reward: float,
              next_state: Any, done: bool, log_prob: float, value: float) -> None:
        self.buffer.append((state, action, reward, next_state, done, log_prob, value))

    def update(self, done: bool, next_value: float = 0) -> Dict:
        if not self.buffer:
            return {}
        states, actions, rewards, next_states, dones, log_probs, values = zip(*self.buffer)
        advantages, returns = self._compute_gae(rewards, values, dones)
        total_actor_loss = 0.0
        total_critic_loss = 0.0
        n_updates = 0
        for s, a, adv, ret in zip(states, actions, advantages, returns):
            if HAS_NUMPY:
                x = np.array(s).flatten()
                adv_val = float(adv)
                ret_val = float(ret)
                probs = self._actor_probs(s)
                grad_logits = np.array([-p for p in probs])
                grad_logits[a] += 1.0
                grad_logits = grad_logits * adv_val
                grad_logits = np.clip(grad_logits, -5.0, 5.0)
                self.actor_w += self.actor_lr * np.outer(x, grad_logits)
                self.actor_b += self.actor_lr * grad_logits
                self.actor_w = np.clip(self.actor_w, -10, 10)
                self.actor_b = np.clip(self.actor_b, -10, 10)
                v_pred = self._critic_value(s)
                error = ret_val - v_pred
                error = max(-10, min(10, error))
                h = np.maximum(0, np.dot(x, self.critic_w1) + self.critic_b1)
                h = np.clip(h, 0, 100)
                grad_w2 = np.outer(h, error)
                grad_b2 = np.array([error])
                self.critic_w2 += self.critic_lr * grad_w2
                self.critic_b2 += self.critic_lr * grad_b2
                grad_h = np.dot(self.critic_w2, error).flatten() * (h > 0)
                grad_h = np.clip(grad_h, -5.0, 5.0)
                grad_w1 = np.outer(x, grad_h)
                grad_b1 = grad_h
                self.critic_w1 += self.critic_lr * grad_w1
                self.critic_b1 += self.critic_lr * grad_b1
                self.critic_w1 = np.clip(self.critic_w1, -10, 10)
                self.critic_b1 = np.clip(self.critic_b1, -10, 10)
                self.critic_w2 = np.clip(self.critic_w2, -10, 10)
                self.critic_b2 = np.clip(self.critic_b2, -10, 10)
                total_actor_loss += float(adv)
                total_critic_loss += float((ret - self._critic_value(s)) ** 2)
                n_updates += 1
        self.buffer.clear()
        return {
            'actor_loss': total_actor_loss / max(n_updates, 1),
            'critic_loss': total_critic_loss / max(n_updates, 1)
        }

    def _compute_gae(self, rewards: Tuple, values: Tuple,
                     dones: Tuple, gamma: float = 0.99, lam: float = 0.95) -> Tuple[List, List]:
        advantages = []
        gae = 0
        for i in reversed(range(len(rewards))):
            next_val = 0 if i == len(rewards) - 1 else values[i + 1]
            delta = rewards[i] + gamma * next_val * (1 - dones[i]) - values[i]
            gae = delta + gamma * lam * (1 - dones[i]) * gae
            advantages.insert(0, gae)
        returns = [adv + val for adv, val in zip(advantages, values)]
        return advantages, returns

class PPO:
    def __init__(self, state_dim: int, action_dim: int, lr: float = 3e-4,
                 gamma: float = 0.99, epsilon: float = 0.2,
                 value_coef: float = 0.5, entropy_coef: float = 0.01,
                 epochs: int = 4, batch_size: int = 64) -> None:
        self.s_dim = state_dim
        self.a_dim = action_dim
        self.lr = lr
        self.gamma = gamma
        self.eps_clip = epsilon
        self.v_coef = value_coef
        self.ent_coef = entropy_coef
        self.epochs = epochs
        self.batch_size = batch_size
        self.buffer = []
        if HAS_NUMPY:
            self.policy = {
                'w': np.random.randn(state_dim, action_dim) * 0.01,
                'b': np.zeros(action_dim)
            }
            self.value = {
                'w1': np.random.randn(state_dim, 64) * np.sqrt(2 / state_dim),
                'b1': np.zeros(64),
                'w2': np.random.randn(64, 1) * np.sqrt(2 / 64),
                'b2': np.zeros(1)
            }
        else:
            self.policy_table = defaultdict(lambda: [1.0 / action_dim] * action_dim)
            self.value_table = defaultdict(float)

    def _policy_probs(self, state: Any) -> Any:
        if HAS_NUMPY:
            x = np.array(state).flatten()
            logits = np.dot(x, self.policy['w']) + self.policy['b']
            exps = np.exp(logits - np.max(logits))
            return exps / exps.sum()
        else:
            key = tuple(state) if isinstance(state, (list, tuple)) else state
            return self.policy_table.get(key, [1.0 / self.a_dim] * self.a_dim)

    def _value(self, state: Any) -> float:
        if HAS_NUMPY:
            x = np.array(state).flatten()
            h = np.maximum(0, np.dot(x, self.value['w1']) + self.value['b1'])
            result = np.dot(h, self.value['w2']) + self.value['b2']
            return float(result.flatten()[0]) if result.size > 0 else 0.0
        else:
            key = tuple(state) if isinstance(state, (list, tuple)) else state
            return self.value_table.get(key, 0.0)

    def select_action(self, state: Any) -> Tuple[int, float, float]:
        probs = self._policy_probs(state)
        if HAS_NUMPY:
            action = int(np.random.choice(self.a_dim, p=probs))
            logp = math.log(max(probs[action], 1e-8))
        else:
            r = random.random()
            cum = 0.0
            action = 0
            for i, p in enumerate(probs):
                cum += p
                if r <= cum:
                    action = i
                    break
            logp = math.log(max(probs[action], 1e-8))
        val = self._value(state)
        return action, logp, val

    def store(self, state: Any, action: int, reward: float,
              next_state: Any, done: bool, logp: float, val: float) -> None:
        self.buffer.append((state, action, reward, next_state, done, logp, val))

    def update(self) -> Dict:
        if not self.buffer:
            return {}
        self.buffer.clear()
        return {'loss': 0.0}

class EnsembleRL:
    def __init__(self, state_dim: int, action_dim: int, use_curiosity: bool = True,
                 use_episodic: bool = True, use_meta: bool = True,
                 weight_opt_freq: int = 100) -> None:
        self.s_dim = state_dim
        self.a_dim = action_dim
        self.algorithms = {
            'dqn': DoubleDQN(state_dim, action_dim),
            'sarsa': SARSAAgent(state_dim, action_dim),
            'ac': ActorCritic(state_dim, action_dim),
            'ppo': PPO(state_dim, action_dim)
        }
        self.weights = {k: 0.25 for k in self.algorithms}
        self.perf = {k: 0.0 for k in self.algorithms}
        self.recent_rewards = {k: deque(maxlen=50) for k in self.algorithms}
        self.step = 0
        self.weight_opt_freq = weight_opt_freq

    def select_action(self, state: Any, exploit_only: bool = False) -> int:
        votes = {}
        for name, algo in self.algorithms.items():
            try:
                a = algo.select_action(state, exploit_only)
                votes[name] = a
            except Exception:
                continue
        if not votes:
            return random.randint(0, self.a_dim - 1)
        wsum = defaultdict(float)
        for name, a in votes.items():
            wsum[a] += self.weights.get(name, 0.25)
        return max(wsum, key=wsum.get)

    def update_weights_by_performance(self) -> None:
        avg_rewards = {}
        for name, dq in self.recent_rewards.items():
            if dq:
                avg_rewards[name] = sum(dq) / len(dq)
            else:
                avg_rewards[name] = 0.0
        for name, r in avg_rewards.items():
            self.perf[name] = 0.9 * self.perf.get(name, 0) + 0.1 * r
        perf_vals = list(self.perf.values())
        max_p = max(perf_vals)
        exp_vals = [math.exp(p - max_p) for p in perf_vals]
        s = sum(exp_vals)
        new_weights = [e / s if s > 0 else 1.0 / len(exp_vals) for e in exp_vals]
        for i, name in enumerate(self.algorithms):
            self.weights[name] = float(new_weights[i])

    def update(self, state: Any, action: int, reward: float,
               next_state: Any, done: bool) -> Dict:
        total_reward = float(reward)
        for name in self.algorithms:
            self.recent_rewards[name].append(total_reward)
        for name, algo in self.algorithms.items():
            try:
                if name == 'dqn':
                    algo.store(state, action, total_reward, next_state, done)
                    if len(algo.memory) >= algo.batch:
                        algo.learn()
                elif name == 'sarsa':
                    next_a = algo.select_action(next_state, exploit_only=False)
                    algo.update(state, action, total_reward, next_state, next_a, done)
                elif name == 'ac':
                    ac_action, logp, val = algo.select_action(state)
                    algo.store(state, ac_action, total_reward, next_state, done, logp, val)
                    if done or len(algo.buffer) >= 32:
                        algo.update(done)
                elif name == 'ppo':
                    ppo_action, logp, val = algo.select_action(state)
                    algo.store(state, ppo_action, total_reward, next_state, done, logp, val)
                    if len(algo.buffer) >= 2048 or done:
                        algo.update()
            except Exception:
                continue
        self.step += 1
        if self.step % self.weight_opt_freq == 0:
            self.update_weights_by_performance()
        return {'total_reward': total_reward}

# ================================================================================
# SECCION 21: LOGICA DIFUSA (FuzzyLogicController)
# ================================================================================
class FuzzyLogicController:
    """Controlador de logica difusa con funciones de membresia triangulares,
    trapezoidales y gaussianas. Soporta reglas AND/OR con defuzzificacion
    por centroides."""
    def __init__(self) -> None:
        self.rules: List[Tuple[Dict[str, str], Dict[str, Any]]] = []
        self.mfs: Dict[str, Dict[str, Tuple[str, Tuple]]] = {}
        self.outputs: Dict[str, Tuple[float, float]] = {}

    def add_mf(self, var: str, name: str, mf_type: str, params: Tuple) -> None:
        self.mfs.setdefault(var, {})[name] = (mf_type, params)

    def add_output(self, var: str, output_range: Tuple[float, float] = (0.0, 1.0)) -> None:
        self.outputs[var] = output_range

    def add_rule(self, antecedent: Dict[str, str], consequent: Dict[str, Any]) -> None:
        self.rules.append((antecedent, consequent))
        for outvar in consequent:
            if outvar not in self.outputs:
                self.outputs[outvar] = (0.0, 1.0)

    def _triangle(self, x: float, a: float, b: float, c: float) -> float:
        if x <= a or x >= c:
            return 0.0
        elif a < x <= b:
            return (x - a) / (b - a) if b != a else 0.0
        else:
            return (c - x) / (c - b) if c != b else 0.0

    def _trapezoid(self, x: float, a: float, b: float, c: float, d: float) -> float:
        if x <= a or x >= d:
            return 0.0
        elif b <= x <= c:
            return 1.0
        elif a < x < b:
            return (x - a) / (b - a) if b != a else 0.0
        else:
            return (d - x) / (d - c) if d != c else 0.0

    def _gauss(self, x: float, c: float, sigma: float) -> float:
        if sigma == 0:
            return 1.0 if x == c else 0.0
        return math.exp(-0.5 * ((x - c) / sigma) ** 2)

    def _eval_mf(self, var: str, name: str, val: float) -> float:
        if var not in self.mfs or name not in self.mfs[var]:
            return 0.0
        mf_type, params = self.mfs[var][name]
        if mf_type == 'triangle':
            return self._triangle(val, *params)
        elif mf_type == 'trapezoid':
            return self._trapezoid(val, *params)
        elif mf_type == 'gaussian':
            return self._gauss(val, *params)
        return 0.0

    def fuzzify(self, inputs: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        fuzzy: Dict[str, Dict[str, float]] = {}
        for var, val in inputs.items():
            if var in self.mfs:
                fuzzy[var] = {name: self._eval_mf(var, name, val) for name in self.mfs[var]}
        return fuzzy

    def evaluate(self, inputs: Dict[str, float],
                 output_range: Tuple[float, float] = (0.0, 1.0)) -> float:
        fuzzy = self.fuzzify(inputs)
        outputs: Dict[str, float] = {}
        rule_activations: Dict[str, float] = {}
        for ant, cons in self.rules:
            activations = []
            valid = True
            for v, mf in ant.items():
                if v in fuzzy and mf in fuzzy[v]:
                    activations.append(fuzzy[v][mf])
                else:
                    valid = False
                    break
            if not valid or not activations:
                continue
            act = min(activations)
            if act <= 0.0:
                continue
            for outvar, outval in cons.items():
                if isinstance(outval, (int, float)):
                    outputs[outvar] = max(outputs.get(outvar, 0.0), act * outval)
                else:
                    rule_activations[outval] = max(rule_activations.get(outval, 0.0), act)
        if not outputs and not rule_activations:
            return (output_range[0] + output_range[1]) / 2.0
        num = 0.0
        den = 0.0
        step = (output_range[1] - output_range[0]) / 100.0
        if step <= 0:
            step = 0.01
        x = output_range[0]
        while x <= output_range[1]:
            max_mem = 0.0
            for outvar, val in outputs.items():
                if isinstance(val, (int, float)):
                    closeness = 1.0 - min(1.0, abs(x - val * (output_range[1] - output_range[0]) - output_range[0]) / (output_range[1] - output_range[0] + 0.001))
                    max_mem = max(max_mem, closeness * val)
            for mf_name, activation in rule_activations.items():
                if 'output' in self.mfs and mf_name in self.mfs.get('output', {}):
                    mf_val = self._eval_mf('output', mf_name, x)
                    max_mem = max(max_mem, min(mf_val, activation))
            num += x * max_mem
            den += max_mem
            x += step
        if den > 0:
            return num / den
        return (output_range[0] + output_range[1]) / 2.0

    def get_info(self) -> Dict[str, Any]:
        return {
            'variables': list(self.mfs.keys()),
            'rules_count': len(self.rules),
            'outputs': list(self.outputs.keys()),
            'mfs_per_variable': {k: len(v) for k, v in self.mfs.items()}
        }

# ================================================================================
# SECCION 22: KALMAN FILTER SIMPLE (fallback sin numpy)
# ================================================================================
class KalmanFilterSimple:
    """Filtro de Kalman generico n-dimensional. Si numpy esta disponible usa
    operaciones vectorizadas; si no, usa listas anidadas."""
    def __init__(self, state_dim: int, obs_dim: int) -> None:
        self.n = state_dim
        self.m = obs_dim
        if HAS_NUMPY:
            self.x = np.zeros(state_dim)
            self.P = np.eye(state_dim)
            self.Q = np.eye(state_dim) * 0.01
            self.R = np.eye(obs_dim) * 0.1
            self.A = np.eye(state_dim)
            self.H = np.eye(obs_dim, state_dim)
        else:
            self.x = [0.0] * state_dim
            self.P = [[1.0 if i == j else 0.0 for j in range(state_dim)] for i in range(state_dim)]
            self.Q = [[0.01 if i == j else 0.0 for j in range(state_dim)] for i in range(state_dim)]
            self.R = [[0.1 if i == j else 0.0 for j in range(obs_dim)] for i in range(obs_dim)]
            self.A = [[1.0 if i == j else 0.0 for j in range(state_dim)] for i in range(state_dim)]
            self.H = [[1.0 if i == j else 0.0 for j in range(state_dim)] for i in range(obs_dim)]

    def predict(self) -> None:
        if HAS_NUMPY:
            self.x = self.A @ self.x
            self.P = self.A @ self.P @ self.A.T + self.Q
        else:
            new_x = [sum(self.A[i][j] * self.x[j] for j in range(self.n)) for i in range(self.n)]
            self.x = new_x
            for i in range(self.n):
                for j in range(self.n):
                    self.P[i][j] = sum(self.A[i][k] * sum(self.P[k][l] * self.A[j][l]
                                                          for l in range(self.n))
                                       for k in range(self.n)) + self.Q[i][j]

    def update(self, z: List[float]) -> None:
        if HAS_NUMPY:
            y = np.array(z) - self.H @ self.x
            S = self.H @ self.P @ self.H.T + self.R
            K = self.P @ self.H.T @ np.linalg.inv(S)
            self.x = self.x + K @ y
            self.P = (np.eye(self.n) - K @ self.H) @ self.P
        else:
            for i in range(min(self.n, len(z))):
                innovation = z[i] - sum(self.H[i][j] * self.x[j] for j in range(self.n))
                self.x[i] += 0.1 * innovation

    def get_state(self) -> Any:
        return self.x

    def get_covariance(self) -> Any:
        return self.P

    def reset(self) -> None:
        if HAS_NUMPY:
            self.x = np.zeros(self.n)
            self.P = np.eye(self.n)
        else:
            self.x = [0.0] * self.n
            self.P = [[1.0 if i == j else 0.0 for j in range(self.n)] for i in range(self.n)]

# ================================================================================
# SECCION 23: OPTIMIZADOR GENETICO
# ================================================================================
class GeneticOptimizer:
    """Optimizador genetico generico con seleccion por torneo, elitismo,
    cruce de un punto y mutacion gaussiana."""
    def __init__(self, param_bounds: Dict[str, Tuple[float, float]],
                 pop_size: int = 50, elite_ratio: float = 0.1,
                 mut_rate: float = 0.1, cross_rate: float = 0.7,
                 gens: int = 100) -> None:
        self.bounds = param_bounds
        self.pop_size = pop_size
        self.elite = int(pop_size * elite_ratio)
        self.mut = mut_rate
        self.cross = cross_rate
        self.gens = gens
        self.best_fitness_history: List[float] = []
        self.avg_fitness_history: List[float] = []

    def _create_individual(self) -> Dict[str, float]:
        ind: Dict[str, float] = {}
        for p, (lo, hi) in self.bounds.items():
            if isinstance(lo, int) and isinstance(hi, int):
                ind[p] = random.randint(lo, hi)
            else:
                ind[p] = random.uniform(lo, hi)
        return ind

    def _mutate(self, ind: Dict[str, float]) -> Dict[str, float]:
        for p in ind:
            if random.random() < self.mut:
                lo, hi = self.bounds[p]
                if isinstance(lo, int) and isinstance(hi, int):
                    ind[p] = int(random.gauss(ind[p], (hi - lo) / 10))
                    ind[p] = max(lo, min(hi, ind[p]))
                else:
                    ind[p] = random.gauss(ind[p], (hi - lo) / 10)
                    ind[p] = max(lo, min(hi, ind[p]))
        return ind

    def _crossover(self, p1: Dict, p2: Dict) -> Tuple[Dict, Dict]:
        if random.random() < self.cross:
            c1, c2 = p1.copy(), p2.copy()
            point = random.choice(list(p1.keys()))
            crossed = False
            for k in p1:
                if k == point:
                    crossed = True
                if crossed:
                    c1[k], c2[k] = p2[k], p1[k]
            return c1, c2
        return p1.copy(), p2.copy()

    def _tournament_selection(self, pop: List[Dict], fits: List[float],
                               k: int = 3) -> List[Dict]:
        selected: List[Dict] = []
        for _ in range(len(pop)):
            idx = random.sample(range(len(pop)), k)
            best_idx = max(idx, key=lambda i: fits[i])
            selected.append(pop[best_idx].copy())
        return selected

    def optimize(self, fitness_fn: Callable[[Dict], float],
                 verbose: bool = False) -> Tuple[Dict[str, float], float]:
        pop = [self._create_individual() for _ in range(self.pop_size)]
        best_ind: Optional[Dict] = None
        best_fit = -float('inf')
        self.best_fitness_history = []
        self.avg_fitness_history = []
        for gen in range(self.gens):
            fits = [fitness_fn(ind) for ind in pop]
            gen_best = max(fits)
            gen_avg = sum(fits) / len(fits)
            self.best_fitness_history.append(gen_best)
            self.avg_fitness_history.append(gen_avg)
            for i, f in enumerate(fits):
                if f > best_fit:
                    best_fit = f
                    best_ind = pop[i].copy()
            selected = self._tournament_selection(pop, fits, k=3)
            new_pop = selected[:self.elite]
            while len(new_pop) < self.pop_size:
                p1, p2 = random.sample(selected, 2)
                c1, c2 = self._crossover(p1, p2)
                c1 = self._mutate(c1)
                c2 = self._mutate(c2)
                new_pop.append(c1)
                if len(new_pop) < self.pop_size:
                    new_pop.append(c2)
            pop = new_pop[:self.pop_size]
            if verbose and gen % max(1, self.gens // 10) == 0:
                log.info("Gen %d: best=%.4f, avg=%.4f", gen, best_fit, gen_avg)
        return best_ind if best_ind is not None else {}, best_fit

    def get_history(self) -> Dict[str, List[float]]:
        return {'best': self.best_fitness_history, 'avg': self.avg_fitness_history}

# ================================================================================
# SECCION 24: HIPERNUMERO AVANZADO
# ================================================================================
class HyperNumberAdvanced:
    """Representacion numerica con soporte para valores reales y modo logaritmico
    para numeros extremadamente grandes. Implementa operadores aritmeticos."""
    def __init__(self, val: float = 0.0) -> None:
        self.sign: int = 1 if val >= 0 else -1
        self.val: float = abs(float(val))
        self.mode: str = "real"
        self.log10: float = 0.0

    def add(self, x: Any) -> None:
        if isinstance(x, HyperNumberAdvanced):
            x = x.to_float()
        xs = 1 if x >= 0 else -1
        x = abs(x)
        if self.mode == "real":
            new = self.sign * self.val + xs * x
            self.sign = 1 if new >= 0 else -1
            self.val = abs(new)
        else:
            self.val += x

    def subtract(self, x: Any) -> None:
        if isinstance(x, HyperNumberAdvanced):
            x = x.to_float()
        self.add(-x)

    def multiply(self, x: Any) -> None:
        if isinstance(x, HyperNumberAdvanced):
            x = x.to_float()
        if x < 0:
            self.sign *= -1
        x = abs(x)
        if self.mode == "real":
            self.val *= x
        else:
            self.log10 += math.log10(x) if x > 0 else 0

    def divide(self, x: Any) -> None:
        if isinstance(x, HyperNumberAdvanced):
            x = x.to_float()
        if x == 0:
            raise ZeroDivisionError("No se puede dividir por cero")
        self.multiply(1.0 / x)

    def power(self, exp: float) -> None:
        val = self.to_float()
        result = val ** exp
        self.sign = 1 if result >= 0 else -1
        self.val = abs(result)

    def to_float(self) -> float:
        if self.mode == "real":
            return self.sign * self.val
        return self.sign * (10 ** self.log10)

    def to_int(self) -> int:
        return int(self.to_float())

    def display(self) -> str:
        if self.mode == "real":
            return "{:.6g}".format(self.sign * self.val)
        return "{}~10^{:.6f}".format('-' if self.sign < 0 else '', self.log10)

    def copy(self) -> 'HyperNumberAdvanced':
        new = HyperNumberAdvanced()
        new.sign = self.sign
        new.val = self.val
        new.mode = self.mode
        new.log10 = self.log10
        return new

    def __repr__(self) -> str:
        return "HyperNumberAdvanced({})".format(self.display())

    def __add__(self, other: Any) -> 'HyperNumberAdvanced':
        result = self.copy()
        result.add(other)
        return result

    def __sub__(self, other: Any) -> 'HyperNumberAdvanced':
        result = self.copy()
        result.subtract(other)
        return result

    def __mul__(self, other: Any) -> 'HyperNumberAdvanced':
        result = self.copy()
        result.multiply(other)
        return result

    def __truediv__(self, other: Any) -> 'HyperNumberAdvanced':
        result = self.copy()
        result.divide(other)
        return result

    def __neg__(self) -> 'HyperNumberAdvanced':
        result = self.copy()
        result.sign *= -1
        return result

    def __abs__(self) -> 'HyperNumberAdvanced':
        result = self.copy()
        result.sign = 1
        return result

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, HyperNumberAdvanced):
            return abs(self.to_float() - other.to_float()) < 1e-10
        return abs(self.to_float() - float(other)) < 1e-10

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, HyperNumberAdvanced):
            return self.to_float() < other.to_float()
        return self.to_float() < float(other)

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, HyperNumberAdvanced):
            return self.to_float() > other.to_float()
        return self.to_float() > float(other)

# ================================================================================
# SECCION 25: PREDICTOR DE DEMANDA
# ================================================================================
class DemandPredictor:
    """Prediccion simple de demanda basada en hora del dia y multiplicadores
    geograficos por zona."""
    def __init__(self) -> None:
        self.hourly_weights: List[float] = [1.0] * 24
        for h in range(7, 10):
            self.hourly_weights[h] = 1.5
        for h in range(17, 20):
            self.hourly_weights[h] = 1.8
        for h in range(0, 5):
            self.hourly_weights[h] = 0.3
        self.location_multipliers: Dict[Tuple[float, float], float] = defaultdict(lambda: 1.0)

    def set_location_multiplier(self, lat_lon_key: Tuple[float, float],
                                 multiplier: float) -> None:
        self.location_multipliers[lat_lon_key] = multiplier

    def predict(self, lat: float, lon: float) -> float:
        now = datetime.now()
        hour = now.hour
        base = self.hourly_weights[hour]
        key = (round(lat, 1), round(lon, 1))
        loc_factor = self.location_multipliers.get(key, 1.0)
        return base * loc_factor

# ================================================================================
# SECCION 26: SESION DE USUARIO (Multiusuario) - VERSION BASE
# ================================================================================
class UserSessionBase:
    """Almacena el estado basico por usuario/conductor. Cada sesion tiene su
    propio SharedDataRegistry y directorio de persistencia."""
    def __init__(self, user_id: str) -> None:
        self.user_id: str = user_id
        self.registry: SharedDataRegistry = SharedDataRegistry()
        self.persist_dir: Path = Path("./gps_symbiosis_data/user_{}".format(user_id))
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.gps_core: Optional['GPSCore'] = None

# ================================================================================
# SECCION 27: CLASE PRINCIPAL (SymbiosisGPS)
# ================================================================================
class SymbiosisGPS:
    """Clase principal que integra todos los modulos: GPS Core, routing,
    matching, RL ensemble, fuzzy, demand predictor, network monitor."""
    def __init__(self, user_session: 'UserSession', use_real_gps: bool = True,
                 allow_sim: bool = False) -> None:
        self.session = user_session
        self.persist_dir: Path = Path("./gps_symbiosis_data/user_{}".format(user_session.user_id))
        self.registry: SharedDataRegistry = self.session.registry
        self._ensure_persist_dir()
        provider = create_gps_provider(use_real=use_real_gps, fallback_to_sim=allow_sim)
        self.gps: GPSCore = GPSCore(provider=provider, use_kalman=True)
        self.gps.start()
        self.routing_graph: RouteGraph = RouteGraph()
        self.routing: RoutingEngine = RoutingEngine(self.routing_graph)
        self.matching: MatchingEngine = MatchingEngine()
        self.network_monitor: NetworkMonitor = NetworkMonitor()
        self.network_monitor.start()
        self.demand_predictor: DemandPredictor = DemandPredictor()
        self.fuzzy: FuzzyLogicController = FuzzyLogicController()
        self._setup_fuzzy()
        self.rl: Optional[EnsembleRL] = None
        self.last_state: Optional[List[float]] = None
        self._load_all()

    def _setup_fuzzy(self) -> None:
        self.fuzzy.add_mf('demand', 'low', 'triangle', (0, 0.3, 0.5))
        self.fuzzy.add_mf('demand', 'high', 'triangle', (0.5, 0.7, 1))
        self.fuzzy.add_rule({'demand': 'high'}, {'decision': 1.0})
        self.fuzzy.add_rule({'demand': 'low'}, {'decision': 0.0})

    def _ensure_persist_dir(self) -> None:
        if not self.persist_dir.exists():
            self.persist_dir.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> None:
        geofence_file = self.persist_dir / "geofences.json"
        if geofence_file.exists():
            try:
                self.gps.geofence.load(str(geofence_file))
            except Exception:
                pass

    def _save_all(self) -> None:
        self._ensure_persist_dir()
        try:
            geofence_file = self.persist_dir / "geofences.json"
            self.gps.geofence.save(str(geofence_file))
        except Exception:
            pass
        if self.rl:
            try:
                rl_file = self.persist_dir / "ensemble_rl.pkl"
                self.rl.save(str(rl_file))
            except Exception:
                pass

    def get_location(self) -> Optional[Coordinate]:
        return self.gps.get_location()

    def update_external_location(self, lat: float, lon: float) -> bool:
        try:
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                return False
            # Sanity check: validar coordenadas
            if lat < -90 or lat > 90 or lon < -180 or lon > 180:
                return False
            if abs(lat) < 0.001 and abs(lon) < 0.001:
                return False
            coord = Coordinate(lat, lon)
            if hasattr(self.gps, 'geofence') and self.gps.geofence:
                self.gps.geofence.update(coord)
            if hasattr(self.gps, '_listeners') and self.gps._listeners:
                for cb in self.gps._listeners:
                    try:
                        cb(coord)
                    except Exception:
                        pass
            if hasattr(self, 'registry') and self.registry:
                self.registry.set("gps:ubicacion_externa", {
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": time.time(),
                    "source": "external"
                })
            return True
        except Exception:
            return False

    def add_node(self, node_id: str, lat: float, lon: float) -> None:
        self.routing_graph.add_node(Node(node_id, lat, lon))

    def add_edge(self, edge_id: str, from_node: str, to_node: str,
                  dist_km: float, time_min: float) -> None:
        self.routing_graph.add_edge(Edge(edge_id, from_node, to_node, dist_km, time_min))

    def route(self, from_node: str, to_node: str,
              objective: str = "time") -> Tuple[List[str], List[str], float]:
        nodes, edges, cost = self.routing.shortest_path(from_node, to_node, objective)
        return nodes, edges, cost

    def init_rl(self, state_dim: int, action_dim: int) -> None:
        self.rl = EnsembleRL(state_dim, action_dim, use_curiosity=True,
                              use_episodic=True, use_meta=True)
        rl_file = self.persist_dir / "ensemble_rl.pkl"
        if rl_file.exists() and rl_file.stat().st_size > 0:
            try:
                self.rl.load(str(rl_file))
            except Exception:
                pass

    def get_current_state_vector(self) -> List[float]:
        loc = self.gps.get_location()
        net = self.registry.get("network:status", {})
        demand = self.demand_predictor.predict(
            loc.latitude if loc else 0,
            loc.longitude if loc else 0
        )
        state = [
            loc.latitude / 180.0 if loc else 0,
            loc.longitude / 360.0 if loc else 0,
            self.gps.get_speed() / 120.0,
            demand,
            float(net.get("connected", 0)),
            float(net.get("latency_ms", 0)) / 1000.0
        ]
        return state[:6]

    def rl_action(self, state: Optional[List[float]] = None) -> int:
        if self.rl is None:
            return 0
        if state is None:
            state = self.get_current_state_vector()
        return self.rl.select_action(state)

    def rl_update(self, state: List[float], action: int, reward: float,
                   next_state: List[float], done: bool) -> None:
        if self.rl is None:
            return
        self.rl.update(state, action, reward, next_state, done)

    def save_rl_model(self) -> None:
        self._ensure_persist_dir()
        if self.rl:
            rl_file = self.persist_dir / "ensemble_rl.pkl"
            self.rl.save(str(rl_file))

    def add_geofence(self, center_lat: float, center_lon: float,
                      radius_km: float, fence_id: Optional[str] = None) -> str:
        if fence_id is None:
            fence_id = str(uuid.uuid4())[:8]
        center = Coordinate(center_lat, center_lon)
        fence = Geofence(fence_id, center, radius_km)
        self.gps.add_geofence(fence)
        return fence_id

    def enable_bluetooth_auto_learning(self, enabled: bool = True) -> None:
        if hasattr(self.gps, 'bluetooth'):
            self.gps.bluetooth.enable_auto_learning(enabled)

    def enable_cellular_auto_learning(self, enabled: bool = True) -> None:
        if hasattr(self.gps, 'cellular'):
            self.gps.cellular.auto_learn_enabled = enabled

    def enable_wifi_auto_learning(self, enabled: bool = True) -> None:
        pass

    def add_known_beacon(self, mac: str, lat: float, lon: float,
                          name: str = "", tx_power: int = -59,
                          env_factor: float = 2.5) -> None:
        if hasattr(self.gps, 'bluetooth'):
            self.gps.bluetooth.add_beacon(mac, lat, lon, name, tx_power, env_factor)

    def add_known_wifi(self, bssid: str, lat: float, lon: float,
                        ssid: str = "", tx_power: Optional[float] = None) -> None:
        if hasattr(self.gps, 'wifi'):
            self.gps.wifi.add_network(bssid, lat, lon, ssid, tx_power)

    def add_known_cell_tower(self, ci: int, tac: int, mcc: int, mnc: int,
                              lat: float, lon: float, radius_m: float = 500.0,
                              confidence: float = 0.5) -> None:
        if hasattr(self.gps, 'cellular'):
            self.gps.cellular.add_tower(ci, tac, mcc, mnc, lat, lon, radius_m, confidence)

    def export_trajectory(self, fmt: str = 'gpx',
                           filename: Optional[str] = None) -> Optional[str]:
        if hasattr(self.gps, 'export_trajectory'):
            return self.gps.export_trajectory(fmt, filename)
        return None

    def get_trajectory_summary(self) -> Dict[str, Any]:
        if hasattr(self.gps, 'exporter'):
            return self.gps.exporter.get_summary()
        return {'points': 0, 'distance_m': 0.0, 'duration_sec': 0.0, 'avg_speed_ms': 0.0}

    def clear_trajectory(self) -> None:
        if hasattr(self.gps, 'exporter'):
            self.gps.exporter.clear()

    def get_system_status(self) -> Dict[str, Any]:
        loc = self.gps.get_location()
        net = self.registry.get("network:status", {})
        external_loc = self.registry.get("gps:ubicacion_externa", {})
        gps_stats = self.gps.get_stats() if hasattr(self.gps, 'get_stats') else {}
        return {
            "location": {
                "latitude": loc.latitude if loc else None,
                "longitude": loc.longitude if loc else None,
                "speed_kmh": self.gps.get_speed()
            },
            "external_location": external_loc,
            "network": net,
            "geofences": self.gps.geofence.get_statistics(),
            "rl_initialized": self.rl is not None,
            "rl_step": self.rl.step if self.rl else 0,
            "gps_stats": gps_stats
        }

    def force_gps_update(self) -> bool:
        try:
            loc = self.gps.provider.get_location()
            if loc:
                self.update_external_location(loc.latitude, loc.longitude)
                return True
            return False
        except Exception:
            return False

    def shutdown(self) -> None:
        self.gps.stop()
        self.network_monitor.stop()
        self._save_all()

# ================================================================================
# SECCION 28: GESTOR DE SESIONES Y CEOIA MULTIUSUARIO
# ================================================================================

# Variables globales para CEOIA
ceoia = None
ceo_avanzado = None

# Parche de seguridad para subprocess.Popen
_orig_popen = subprocess.Popen

def _safe_popen(*args, **kwargs):
    try:
        return _orig_popen(*args, **kwargs)
    except FileNotFoundError as e:
        if 'svc' in str(e).lower():
            return None
        raise

subprocess.Popen = _safe_popen


def _forzar_inicializacion_ceoia():
    global ceoia, ceo_avanzado
    if 'ceoia' not in globals():
        ceoia = None
    if 'ceo_avanzado' not in globals():
        ceo_avanzado = None
    if ceoia is not None or ceo_avanzado is not None:
        return True
    try:
        import importlib
        mod = importlib.import_module("parte5_daimon_base")
        func = getattr(mod, "iniciar_ceoia_unificada", None)
        if callable(func):
            instancia = func()
            if instancia:
                ceoia = instancia
                ceo_avanzado = instancia
                return True
    except Exception:
        pass

    class MockCEOIA:
        def __init__(self):
            self.estado_interno = {'modo_operacion': 'MOCK', 'confianza_decisiones': 0.5}
            self.permisos = {'controlar_gps': True}

        def recibir_orden(self, orden):
            return "Mock procesando: {}".format(orden)

        def recibir_orden_ollama(self, orden):
            return "Simulacro de Ollama: {}".format(orden)

    ceoia = MockCEOIA()
    ceo_avanzado = ceoia
    return False

_forzar_inicializacion_ceoia()


# Gestor de sesiones
_sessions: Dict[str, 'UserSession'] = {}
_sessions_lock = threading.RLock()


class UserSession:
    """Almacena el estado de un conductor/usuario."""
    def __init__(self, user_id: str) -> None:
        self.user_id: str = user_id
        self.registry: SharedDataRegistry = SharedDataRegistry()
        self.estado_conductor: str = "IDLE"
        self.ultima_zona: str = "z1"
        self.web_accessed: bool = False
        self.ia_ready: bool = False
        self.mejor_opcion_prompt_activo: bool = False
        self.ultimos_datos_mapa: Dict[str, Any] = {}
        self.blockchain: List[Dict] = []
        self.numero_bloque: int = 1
        self.bloques_virales: int = 0
        self.mining_log: deque = deque(maxlen=100)
        self.beneficiario_actual: str = user_id
        self.uber_coins: HyperNumberAdvanced = HyperNumberAdvanced(0.0)
        self.q_table: Dict = {}
        self.q_table_lock = threading.RLock()
        self.symbiosis: Optional['SymbiosisGPS'] = None
        self.last_activity: float = time.time()
        self.mining_lock = threading.RLock()
        self.ceoia = None


def get_or_create_session(user_id: str) -> UserSession:
    with _sessions_lock:
        if user_id not in _sessions:
            _sessions[user_id] = UserSession(user_id)
            try:
                sess = _sessions[user_id]
                sess.symbiosis = SymbiosisGPS(
                    user_session=sess,
                    use_real_gps=False,
                    allow_sim=True
                )
                # Configuracion inicial de nodos y aristas
                sess.symbiosis.add_node("albrook", 8.985, -79.52)
                sess.symbiosis.add_node("arraijan", 8.88, -79.76)
                sess.symbiosis.add_node("chorrera", 8.875, -79.78)
                sess.symbiosis.add_node("sancarlos", 8.89, -79.80)
                sess.symbiosis.add_node("veracruz", 8.85, -79.82)
                sess.symbiosis.add_edge("albrook_arraijan", "albrook", "arraijan", 15.0, 25.0)
                sess.symbiosis.add_edge("arraijan_chorrera", "arraijan", "chorrera", 12.0, 20.0)
                sess.symbiosis.add_edge("chorrera_sancarlos", "chorrera", "sancarlos", 8.0, 15.0)
                sess.symbiosis.add_edge("sancarlos_veracruz", "sancarlos", "veracruz", 10.0, 18.0)
                sess.symbiosis.add_edge("albrook_veracruz", "albrook", "veracruz", 25.0, 40.0)
                sess.symbiosis.add_edge("albrook_chorrera", "albrook", "chorrera", 35.0, 55.0)
                # Geocercas por zona
                sess.symbiosis.add_geofence(8.985, -79.52, 3.0, "z1_albrook")
                sess.symbiosis.add_geofence(8.88, -79.76, 3.0, "z2_arraijan")
                sess.symbiosis.add_geofence(8.875, -79.78, 3.0, "z3_chorrera")
                sess.symbiosis.add_geofence(8.89, -79.80, 3.0, "z4_sancarlos")
                sess.symbiosis.add_geofence(8.85, -79.82, 3.0, "z5_veracruz")
                # Inicializar RL
                sess.symbiosis.init_rl(6, 3)
                # Multiplicadores de demanda por zona
                sess.symbiosis.demand_predictor.set_location_multiplier((8.9, -79.5), 1.8)
                sess.symbiosis.demand_predictor.set_location_multiplier((8.8, -79.7), 1.2)
                sess.symbiosis.demand_predictor.set_location_multiplier((8.8, -79.8), 1.0)
            except Exception:
                pass
        sess = _sessions[user_id]
        sess.last_activity = time.time()
        return sess


def get_session(user_id: str) -> Optional[UserSession]:
    with _sessions_lock:
        sess = _sessions.get(user_id)
        if sess:
            sess.last_activity = time.time()
        return sess


def cleanup_old_sessions(max_age_seconds: int = 3600) -> None:
    now = time.time()
    with _sessions_lock:
        to_delete = [uid for uid, sess in _sessions.items()
                     if now - sess.last_activity > max_age_seconds]
        for uid in to_delete:
            if _sessions[uid].symbiosis:
                try:
                    _sessions[uid].symbiosis.shutdown()
                except Exception:
                    pass
            del _sessions[uid]


# Datos estaticos compartidos
ZONAS: List[Dict[str, Any]] = [
    {"id": "z1", "nombre": "Albrook Mall", "lat_min": 8.97, "lat_max": 9.00,
     "lon_min": -79.54, "lon_max": -79.50},
    {"id": "z2", "nombre": "Arraijan Centro", "lat_min": 8.86, "lat_max": 8.90,
     "lon_min": -79.78, "lon_max": -79.74},
    {"id": "z3", "nombre": "La Chorrera Centro", "lat_min": 8.86, "lat_max": 8.89,
     "lon_min": -79.80, "lon_max": -79.76},
    {"id": "z4", "nombre": "San Carlos", "lat_min": 8.87, "lat_max": 8.90,
     "lon_min": -79.82, "lon_max": -79.78},
    {"id": "z5", "nombre": "Veracruz", "lat_min": 8.84, "lat_max": 8.87,
     "lon_min": -79.84, "lon_max": -79.80},
]

ALGO_WEIGHTS: Dict[str, float] = {
    'tasa_de_aceptacion': 5.0, 'tasa_de_finalizacion': 10.0,
    'calificacion_promedio': 2.0, 'viajes_completados': 0.1,
    'tiempo_en_linea': 0.5, 'tasa_de_cancelacion': -20.0,
    'idle_time_ratio': -10.0, 'peak_hours_ratio': 3.0,
    'distance_traveled': 0.05, 'distancia': 0.2,
    'duracion': 0.01, 'tarifa': 1.0,
    'ganancias_reales': 1.0, 'ganancias_estimadas': 0.95,
    'tiempo_de_espera': -0.5, 'costo_de_busqueda_adicional': -0.5,
    'viral_score_bonus': 50.0, 'recompensa_viral': 1.0,
    'best_option_bonus': 25.0, 'engagement_rate': 15.0,
    'share_ratio': 25.0, 'completion_rate_video': 20.0,
    'creativity_bonus': 40.0,
}

MEJOR_OPCION_PROMPT_TEXTO = """
<system_directive lang="dsl-decision-engine" version="4.0">
<!-- Prompt de mejor opcion activado -->
</system_directive>
"""

respuesta_ia = "Prompt activado"

_system_log: deque = deque(maxlen=200)
_system_log_lock = threading.RLock()


def log_message(mensaje: str, usuario_id: Optional[str] = None) -> None:
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    formatted_line = "[{}] {}".format(timestamp, mensaje)
    print(formatted_line, flush=True)
    if usuario_id is None:
        with _system_log_lock:
            _system_log.append({"ts": timestamp, "message": mensaje})
    else:
        sess = get_session(usuario_id)
        if sess:
            with sess.mining_lock:
                sess.mining_log.append({"ts": timestamp, "message": mensaje})


def get_system_logs(limit: int = 50) -> List[Dict]:
    with _system_log_lock:
        return list(_system_log)[-limit:]


def _importar_ceoia_seguro() -> bool:
    global ceoia, ceo_avanzado
    import importlib
    if 'ceoia' not in globals():
        ceoia = None
    if 'ceo_avanzado' not in globals():
        ceo_avanzado = None
    if ceoia is not None or ceo_avanzado is not None:
        return True
    posibles_modulos = ['part5_daimon_base', 'parte5_daimon_base']
    for nombre_modulo in posibles_modulos:
        try:
            modulo = importlib.import_module(nombre_modulo)
            iniciar_func = getattr(modulo, 'iniciar_ceoia_unificada', None)
            if callable(iniciar_func):
                instancia = iniciar_func()
                if instancia:
                    ceoia = instancia
                    ceo_avanzado = instancia
                    return True
            if getattr(modulo, 'ceoia', None) is not None:
                ceoia = modulo.ceoia
            if getattr(modulo, 'ceo_avanzado', None) is not None:
                ceo_avanzado = modulo.ceo_avanzado
            if ceoia is not None or ceo_avanzado is not None:
                return True
        except Exception:
            pass
    return False

_importar_ceoia_seguro()


def get_ceo_instance():
    return ceo_avanzado if ceo_avanzado is not None else ceoia


def notificar_parte1(mensaje: str) -> None:
    try:
        import main
        if hasattr(main, 'procesar_orden_mejor_opcion'):
            main.procesar_orden_mejor_opcion(mensaje)
            return
        elif hasattr(main, 'recibir_orden'):
            main.recibir_orden(mensaje)
            return
    except ImportError:
        pass
    try:
        import parte1_modulo_principal
        if hasattr(parte1_modulo_principal, 'procesar_orden_mejor_opcion'):
            parte1_modulo_principal.procesar_orden_mejor_opcion(mensaje)
        elif hasattr(parte1_modulo_principal, 'recibir_orden'):
            parte1_modulo_principal.recibir_orden(mensaje)
    except ImportError:
        pass


def get_recent_logs(usuario_id: str, limit: int = 50) -> List[Dict]:
    sess = get_session(usuario_id)
    if sess:
        with sess.mining_lock:
            return list(sess.mining_log)[-limit:]
    return []


def simular_metricas_viaje(usuario_id: str) -> Dict[str, Any]:
    sess = get_session(usuario_id)
    beneficiario = sess.beneficiario_actual if sess else "desconocido"
    return {
        'tasa_de_aceptacion': round(random.uniform(0.90, 1.00), 3),
        'tasa_de_finalizacion': round(random.uniform(0.95, 0.99), 3),
        'avg_rating': round(random.uniform(4.90, 5.00), 2),
        'viajes_completados': random.randint(50, 150),
        'tiempo_en_linea': round(random.uniform(8.0, 12.0), 2),
        'tasa_de_cancelacion': round(random.uniform(0.00, 0.02), 3),
        'idle_time_ratio': round(random.uniform(0.05, 0.20), 3),
        'peak_hours_ratio': round(random.uniform(0.6, 1.0), 2),
        'distancia_recorrida': round(random.uniform(200.0, 400.0), 1),
        'viral_score': round(random.uniform(0.5, 1.0), 2),
        'recompensa_viral': round(random.uniform(10.0, 50.0), 2),
        'tasa_de_participacion': round(random.uniform(3.0, 15.0), 2),
        'share_ratio': round(random.uniform(0.05, 0.30), 3),
        'completion_rate_video': round(random.uniform(0.60, 0.95), 2),
        'creativity_score': round(random.uniform(0.7, 1.3), 2),
        'tarifa': round(random.uniform(3.0, 15.0), 2),
        'ganancias_estimadas': round(random.uniform(5.0, 50.0), 2),
        'ganancias_reales': round(random.uniform(5.0, 50.0), 2),
        'waitTime': round(random.uniform(0.0, 2.0), 2),
        'additionalSearchCost': round(random.uniform(0.0, 1.0), 2),
        'startLocation': {
            'latitude': round(random.uniform(8.85, 8.99), 6),
            'longitude': round(random.uniform(-79.80, -79.52), 6)
        },
        'endLocation': {
            'latitude': round(random.uniform(8.85, 8.99), 6),
            'longitude': round(random.uniform(-79.80, -79.52), 6)
        },
        'fareUnit': random.choice(['km', 'millas']),
        'currentTime': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'plataforma': random.choice(['tiktok', 'instagram', 'youtube', 'x', 'web_generica']),
        'usuario_propietario': beneficiario,
    }


def calcular_recompensa_por_viaje(metrics: Dict[str, Any]) -> float:
    recompensa = 0.0
    for metrica, valor in metrics.items():
        if metrica in ALGO_WEIGHTS and isinstance(valor, (int, float)):
            recompensa += float(valor) * float(ALGO_WEIGHTS[metrica])
    viral = metrics.get('viral_score', 0)
    participacion = metrics.get('tasa_de_participacion', 0)
    creatividad = metrics.get('creativity_score', 0)
    impulso = (viral * 0.3 + participacion * 0.4 + creatividad * 0.3) / 100.0
    return round(max(recompensa * (1 + impulso * 0.5), 0.0), 2)


_zona_estado: Dict[str, Dict[str, Any]] = {
    z["id"]: {
        "color": "gris", "ganancia_estimada": 0.0, "tiempo_espera": 0.0,
        "demanda": random.randint(10, 100), "oferta": random.randint(5, 80),
        "ratio_demanda": 0.0
    } for z in ZONAS
}
_zona_estado_lock = threading.RLock()


def minar_bloque_por_publicacion_controlado(
    usuario_id: str,
    url_real_proporcionada: Optional[str] = None,
    usuario_nombre: Optional[str] = None
) -> Dict[str, Any]:
    sess = get_session(usuario_id)
    if not sess:
        return {"error": "Sesion no encontrada"}
    usuario_final = usuario_nombre if usuario_nombre else sess.beneficiario_actual
    if not url_real_proporcionada:
        return {
            'usuario': usuario_final,
            'numero_bloque': sess.numero_bloque,
            'timestamp': time.time(),
            'metrics': simular_metricas_viaje(usuario_id),
            'base_reward': 5.0,
            'bonus_modo_viral': 10.0,
            'bonus_zona': 5.0,
            'zona': sess.ultima_zona,
            'color_zona': get_zona_color(sess.ultima_zona),
            'recompensa': 20.0,
            'block_id': str(uuid.uuid4())[:8],
            'url': "https://ejemplo.com/simulado",
            'plataforma': "simulada"
        }
    metrics = simular_metricas_viaje(usuario_id)
    metrics["url"] = url_real_proporcionada
    metrics["usuario"] = usuario_final
    reward_coins = calcular_recompensa_por_viaje(metrics)
    color = get_zona_color(sess.ultima_zona)
    bonus_zona = 25.0 if color == "rojo" else 15.0 if color == "naranja" else 0.0
    bonificacion_modo_viral = 15.0
    recompensa_total = reward_coins + bonificacion_modo_viral + bonus_zona
    with sess.mining_lock:
        sess.blockchain.append({
            'usuario': usuario_final,
            'numero_bloque': sess.numero_bloque,
            'timestamp': time.time(),
            'metrics': metrics,
            'base_reward': reward_coins,
            'bonus_modo_viral': bonificacion_modo_viral,
            'bonus_zona': bonus_zona,
            'zona': sess.ultima_zona,
            'color_zona': color,
            'recompensa': recompensa_total,
            'block_id': str(uuid.uuid4())[:8],
            'url': url_real_proporcionada,
            'plataforma': metrics.get('plataforma', 'desconocida')
        })
        sess.numero_bloque += 1
        sess.uber_coins.add(recompensa_total)
    return {
        'usuario': usuario_final,
        'numero_bloque': sess.numero_bloque - 1,
        'timestamp': time.time(),
        'metrics': metrics,
        'base_reward': reward_coins,
        'bonus_modo_viral': bonificacion_modo_viral,
        'bonus_zona': bonus_zona,
        'zona': sess.ultima_zona,
        'color_zona': color,
        'recompensa': float(recompensa_total),
        'block_id': str(uuid.uuid4())[:8],
        'url': url_real_proporcionada,
        'plataforma': metrics.get('plataforma', 'desconocida')
    }


def get_zona_color(zona_id: str) -> str:
    with _zona_estado_lock:
        return _zona_estado.get(zona_id, {}).get("color", "gris")


def set_zona_color(zona_id: str, color: str) -> None:
    with _zona_estado_lock:
        if zona_id in _zona_estado:
            _zona_estado[zona_id]["color"] = color


def actualizar_zona_demanda(zona_id: str, demanda: float) -> None:
    with _zona_estado_lock:
        if zona_id not in _zona_estado:
            return
        _zona_estado[zona_id]["demanda"] = demanda
        if demanda > 1.5:
            _zona_estado[zona_id]["color"] = "rojo"
        elif demanda > 1.0:
            _zona_estado[zona_id]["color"] = "naranja"
        elif demanda > 0.5:
            _zona_estado[zona_id]["color"] = "amarillo"
        else:
            _zona_estado[zona_id]["color"] = "gris"


def encontrar_puerto_libre(base: int = 8080, max_intentos: int = 10) -> int:
    for i in range(max_intentos):
        puerto = base + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    return base


# ================================================================================
# SECCION 29: PROCESAMIENTO DE DATOS DEL MAPA CON GPS SYMBIOSIS (MULTIUSUARIO)
# ================================================================================

def procesar_datos_mapa_con_gps(datos_mapa: Dict[str, Any], usuario_id: str) -> Dict[str, Any]:
    resultado: Dict[str, Any] = {
        "gps_procesado": False,
        "zona_detectada": None,
        "demanda_predicha": 0.0,
        "geocercas_activas": [],
        "rl_decision": None,
        "ruta_optima": None,
        "costo_ruta": 0.0
    }
    sess = get_session(usuario_id)
    if not sess or not sess.symbiosis:
        return resultado
    symb = sess.symbiosis
    gps_registry = symb.registry
    try:
        lat = datos_mapa.get('latitude')
        lon = datos_mapa.get('longitude')
        if lat and lon:
            coord = Coordinate(float(lat), float(lon))
            if gps_registry:
                gps_registry.set("gps:ubicacion_actual", {
                    "lat": float(lat),
                    "lon": float(lon),
                    "speed": datos_mapa.get('speed_kmh', 0.0),
                    "rain": datos_mapa.get('rain_active', False)
                })
            if symb.gps.geofence:
                estados = symb.gps.geofence.get_active_fences(coord)
                resultado["geocercas_activas"] = [f.id for f in estados]
                for fence in estados:
                    if "z1" in fence.id:
                        resultado["zona_detectada"] = "z1"
                    elif "z2" in fence.id:
                        resultado["zona_detectada"] = "z2"
                    elif "z3" in fence.id:
                        resultado["zona_detectada"] = "z3"
                    elif "z4" in fence.id:
                        resultado["zona_detectada"] = "z4"
                    elif "z5" in fence.id:
                        resultado["zona_detectada"] = "z5"
            if symb.demand_predictor:
                resultado["demanda_predicha"] = symb.demand_predictor.predict(float(lat), float(lon))
            if resultado["zona_detectada"]:
                demanda = resultado["demanda_predicha"]
                actualizar_zona_demanda(resultado["zona_detectada"], demanda)
            if symb.rl:
                state = symb.get_current_state_vector()
                accion = symb.rl_action(state)
                decisiones = {0: "ACEPTAR", 1: "RECHAZAR", 2: "ESPERAR"}
                resultado["rl_decision"] = decisiones.get(accion, "DESCONOCIDO")
                tarifa = datos_mapa.get('tarifa', 0.0)
                recompensa = tarifa * 0.1 if accion == 0 else (-tarifa * 0.05)
                next_state = symb.get_current_state_vector()
                symb.rl_update(state, accion, recompensa, next_state, False)
            resultado["gps_procesado"] = True
    except Exception:
        pass
    return resultado

# ================================================================================
# SECCION 30: CONFIGURACION FLASK Y ENDPOINTS INTEGRADOS
# ================================================================================

# Puerto dinámico (siempre disponible, incluso sin Flask)
HTTP_PORT = int(os.getenv('PORT', 8080))

# Solo configuramos Flask si está disponible
if HAS_FLASK and app is not None:
    # Configurar CORS
    try:
        from flask_cors import CORS
        CORS(app, resources={r"/*": {"origins": "*"}})
    except ImportError:
        # Fallback manual si CORS no está instalado
        @app.after_request
        def add_cors_headers(response):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response

    # ============================================================
    # FUNCIÓN AUXILIAR PARA OBTENER USER-ID
    # ============================================================
    def _get_user_id_from_request() -> str:
        user_id = request.headers.get('X-User-ID')
        if user_id:
            return user_id
        user_id = request.args.get('usuario')
        if user_id:
            return user_id
        if request.is_json:
            data = request.get_json(silent=True) or {}
            user_id = data.get('usuario')
            if user_id:
                return user_id
        return 'anonimo'

    # ============================================================
    # RUTAS DEL PUENTE - MAPA PRO COMO INTERFAZ PRINCIPAL
    # ============================================================
    @app.route('/')
    def index():
        from flask import redirect
        return redirect('/puente')

    @app.route('/puente')
    def puente():
        from flask import send_from_directory
        try:
            return send_from_directory('static', 'mapa_pro.html')
        except Exception as e:
            return f"""
            <html>
            <head><title>Puente - Error</title></head>
            <body style="background:#0a0a0f;color:#fff;font-family:sans-serif;padding:20px;">
            <h1>Puente Uber Daimon</h1>
            <p style="color:#ff4466;">Error: No se encontro el archivo mapa_pro.html</p>
            <p style="color:#88a;">Asegurate de que el archivo este en la carpeta 'static/'</p>
            <p style="color:#88a;">Error: {str(e)}</p>
            <hr>
            <p><a href="/health" style="color:#4d94ff;">Ver estado del sistema</a></p>
            </body>
            </html>
            """

    @app.route('/mapa_pro')
    def mapa_pro_redirect():
        from flask import redirect
        return redirect('/puente')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    # ============================================================
    # ENDPOINTS DE LA API
    # ============================================================
    @app.route('/ceoia/orden', methods=['POST', 'OPTIONS'])
    def endpoint_ceoia_orden_frontend():
        if request.method == 'OPTIONS':
            return '', 204
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess:
            return jsonify({"exito": False, "error": "Sesion no encontrada"}), 404
        target_ceoia = sess.ceoia if hasattr(sess, 'ceoia') and sess.ceoia else (ceo_avanzado or ceoia)
        if target_ceoia is None:
            return jsonify({"exito": False, "error": "CEOIA no disponible"}), 500
        data = request.get_json(silent=True) or {}
        orden = data.get('orden', '')
        try:
            if hasattr(target_ceoia, 'recibir_orden'):
                resultado = target_ceoia.recibir_orden(orden)
                return jsonify(resultado)
            else:
                return jsonify({"exito": True, "mensaje": "Orden recibida (Modo Simulado)", "orden": orden})
        except Exception as e:
            return jsonify({"exito": False, "error": str(e)}), 500

    @app.route('/health')
    def health_check():
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess:
            return jsonify({"error": "Sesion no encontrada"}), 404
        gps_status = {}
        if sess.symbiosis:
            gps_status = sess.symbiosis.get_system_status()
        return jsonify({
            "estado": "ok",
            "timestamp": float(time.time()),
            "uber_coins": float(sess.uber_coins.to_float()) if hasattr(sess.uber_coins, 'to_float') else 0.0,
            "blocks_mined": int(len(sess.blockchain)),
            "logs_buffer_size": int(len(sess.mining_log)),
            "gps_symbiosis": gps_status,
            "gps_available": True
        }), 200

    @app.route('/ceoia/singularidad', methods=['POST', 'OPTIONS'])
    def ceoia_singularidad():
        if request.method == 'OPTIONS':
            return '', 204
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess:
            return jsonify({"error": "Sesion no encontrada"}), 404
        confianza_base = round(random.uniform(0.75, 0.98), 2)
        if sess.symbiosis and sess.symbiosis.rl:
            confianza_base = sess.symbiosis.rl.weights.get('dqn', 0.85)
        return jsonify({
            "exito": True,
            "singularidad_activa": True,
            "confianza": confianza_base,
            "modo_operacion": "AUTONOMO",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mensaje": "Singularidad Omega sincronizada con GPS Symbiosis."
        }), 200

    @app.route('/api/logs', methods=['GET'])
    def api_get_logs():
        user_id = _get_user_id_from_request()
        limite = request.args.get('limit', 50, type=int)
        logs = get_recent_logs(user_id, limite)
        return jsonify({"success": True, "count": limite, "logs": logs}), 200

    @app.route('/ia/consultar', methods=['POST', 'OPTIONS'])
    def ia_consultar():
        if request.method == 'OPTIONS':
            return '', 204
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess:
            return jsonify({"error": "Sesion no encontrada"}), 404
        data = request.get_json(silent=True) or {}
        pregunta = data.get('pregunta', data.get('query', 'Sin consulta'))
        contexto: Dict[str, Any] = {
            "zona": sess.ultima_zona,
            "monedas": sess.uber_coins.to_float() if hasattr(sess.uber_coins, 'to_float') else 0.0,
            "modo": sess.estado_conductor
        }
        if sess.symbiosis:
            loc = sess.symbiosis.get_location()
            if loc:
                contexto["ubicacion"] = {"lat": loc.latitude, "lon": loc.longitude}
                contexto["demanda"] = sess.symbiosis.demand_predictor.predict(loc.latitude, loc.longitude)
        return jsonify({
            "exito": True,
            "respuesta": f"Procesando: '{pregunta}' | Daimon IA + GPS Symbiosis analizando contexto...",
            "tiempo_respuesta_ms": random.randint(120, 450),
            "estado": "OK",
            "contexto": contexto
        }), 200

    @app.route('/start_mining_socialcoin', methods=['POST', 'OPTIONS'])
    def start_mining_socialcoin():
        if request.method == 'OPTIONS':
            return '', 204
        user_id = _get_user_id_from_request()
        sess = get_or_create_session(user_id)
        data = request.get_json(silent=True) or {}
        url = data.get('url', data.get('video_url', data.get('link', '')))
        usuario_nombre = data.get('usuario', sess.beneficiario_actual)
        bloque = minar_bloque_por_publicacion_controlado(
            usuario_id=user_id,
            url_real_proporcionada=url if url else None,
            usuario_nombre=usuario_nombre
        )
        return jsonify({
            "success": True,
            "mensaje": "Mineria SocialCoin procesada",
            "usuario": usuario_nombre,
            "recompensa": float(bloque.get('recompensa', 0.0)),
            "bloque_numero": int(bloque.get('numero_bloque', 0)),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200

    @app.route('/api/v1/network')
    def obtener_estado_de_red():
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess or not sess.symbiosis:
            return jsonify({
                "status": random.choice(['EXCELENTE', 'ESTABLE', 'SATURADO', 'Offline']),
                "ganador": random.choice(['WiFi', '4G', '5G', 'Ethernet']),
                "latencia": round(random.uniform(0.01, 0.15), 4),
                "internet_ok": True,
                "gps_symbiosis_net": False
            }), 200
        gps_registry = sess.symbiosis.registry
        net_status = gps_registry.get("network:status")
        if net_status:
            return jsonify({
                "status": "EXCELENTE" if net_status.get("connected") else "Offline",
                "ganador": net_status.get("server", "WiFi"),
                "latencia": round(float(net_status.get("latency_ms", 0)) / 1000, 4),
                "internet_ok": net_status.get("connected", False),
                "gps_symbiosis_net": True
            }), 200
        else:
            return jsonify({
                "status": "CONECTANDO",
                "ganador": "Desconocido",
                "latencia": 0.0,
                "internet_ok": False,
                "gps_symbiosis_net": True
            }), 200

    @app.route('/ceoia/estado')
    def get_ceoia_estado():
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess:
            return jsonify({"error": "Sesion no encontrada"}), 404
        extra: Dict[str, Any] = {}
        if sess.symbiosis and sess.symbiosis.rl:
            extra = {
                "rl_weights": sess.symbiosis.rl.weights,
                "rl_step": sess.symbiosis.rl.step
            }
        return jsonify({
            "estado_interno": {
                "modo_operacion": random.choice(['AUTONOMO', 'ASISTENTE', 'IDLE']),
                "confianza_decisiones": round(random.uniform(0.5, 0.95), 2)
            },
            "gps_symbiosis": extra
        }), 200

    @app.route('/uber/activar_mejor_opcion', methods=['POST', 'OPTIONS'])
    def activar_mejor_opcion():
        if request.method == 'OPTIONS':
            return '', 204
        user_id = _get_user_id_from_request()
        sess = get_or_create_session(user_id)
        print("\n" + "=" * 70, flush=True)
        print(" SISTEMA MEJOR OPCION - ACTIVADO", flush=True)
        print("=" * 70, flush=True)
        if 'MEJOR_OPCION_PROMPT_TEXTO' in globals():
            prompt = MEJOR_OPCION_PROMPT_TEXTO
            print(prompt.strip(), flush=True)
        else:
            print(" [ERROR] Prompt no disponible", flush=True)
        print("=" * 70, flush=True)
        print(" Modo PRO activado - Sistema listo", flush=True)
        print("=" * 70 + "\n", flush=True)
        try:
            subprocess.run(
                ["termux-tts-speak", "Protocolo de Mejor Opcion Activado"],
                timeout=10, capture_output=True, check=False
            )
        except Exception:
            pass
        try:
            ceo = get_ceo_instance()
            if ceo:
                if hasattr(ceo, 'recibir_orden_ollama'):
                    ceo.recibir_orden_ollama(prompt)
                elif hasattr(ceo, 'recibir_orden'):
                    ceo.recibir_orden(prompt)
        except Exception:
            pass
        notificar_parte1(prompt)
        if sess.symbiosis and sess.symbiosis.rl:
            for name in sess.symbiosis.rl.algorithms:
                if hasattr(sess.symbiosis.rl.algorithms[name], 'epsilon'):
                    sess.symbiosis.rl.algorithms[name].epsilon = 0.05
        sess.mejor_opcion_prompt_activo = True
        sess.estado_conductor = "MEJOR_OPCION"
        return jsonify({
            "success": True,
            "message": "Protocolo Mejor Opcion activado",
            "estado": sess.estado_conductor,
            "zona_actual": sess.ultima_zona,
            "timestamp": time.time()
        }), 200

    @app.route('/api/v1/miner', methods=['POST', 'OPTIONS'])
    def minerar():
        if request.method == 'OPTIONS':
            return '', 204
        user_id = _get_user_id_from_request()
        sess = get_or_create_session(user_id)
        data = request.get_json(silent=True) or {}
        url = data.get('url', data.get('video_url', ''))
        usuario_nombre = data.get('usuario', sess.beneficiario_actual)
        try:
            bloque = minar_bloque_por_publicacion_controlado(
                usuario_id=user_id,
                url_real_proporcionada=url if url else None,
                usuario_nombre=usuario_nombre
            )
            resumen = (
                f"Nuevo bloque minado. Usuario: {usuario_nombre}, "
                f"Recompensa: {bloque.get('recompensa', 0):.2f}, "
                f"Zona: {bloque.get('zona')}, "
                f"URL: {url or 'automatica'}"
            )
            try:
                ceo = get_ceo_instance()
                if ceo and hasattr(ceo, 'recibir_orden'):
                    ceo.recibir_orden(resumen)
            except Exception:
                pass
            notificar_parte1(resumen)
            if sess.symbiosis and random.random() < 0.1:
                sess.symbiosis.save_rl_model()
            return jsonify({
                "exito": True,
                "bloque": bloque.get('numero_bloque'),
                "recompensa": float(bloque.get('recompensa', 0.0)),
                "zona": bloque.get('zona'),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 200
        except Exception:
            return jsonify({"exito": False, "error": "Error interno de mineria"}), 500

    @app.route('/api/mapa/update', methods=['POST'])
    def recibir_datos_mapa():
        user_id = _get_user_id_from_request()
        sess = get_or_create_session(user_id)
        data = request.get_json(silent=True) or {}
        sess.ultimos_datos_mapa = {
            'tarifa': data.get('tarifa', 0.0),
            'distancia_km': data.get('distancia_km', 0.0),
            'waiting_min': data.get('waiting_min', 0.0),
            'speed_kmh': data.get('speed_kmh', 0.0),
            'rain_active': data.get('rain_active', False),
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude'),
            'viaje_activo': data.get('viaje_activo', False),
            'multiplicador': data.get('multiplicador', 1.0),
            'timestamp': time.time(),
            'total_daily': data.get('total_daily', 0.0),
            'fuel_cost_daily': data.get('fuel_cost_daily', 0.0),
            'costo_fijo_diario': data.get('costo_fijo_diario', 0.0),
            'costo_km': data.get('costo_km', 0.0),
            'engine_size': data.get('engine_size', '1.8'),
            'mileage': data.get('mileage', 10.0),
            'daily_km': data.get('daily_km', 0.0),
        }
        resultado_gps = procesar_datos_mapa_con_gps(sess.ultimos_datos_mapa, usuario_id=user_id)
        if resultado_gps.get("zona_detectada"):
            sess.ultima_zona = resultado_gps["zona_detectada"]
        try:
            if ceo_avanzado and hasattr(ceo_avanzado, 'analizar_datos_mapa'):
                ceo_avanzado.analizar_datos_mapa(sess.ultimos_datos_mapa)
        except Exception:
            pass
        return jsonify({
            "estado": "ok",
            "gps_symbiosis": resultado_gps
        })

    @app.route('/api/map/datos')
    def obtener_datos_mapa():
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess:
            return jsonify({"error": "Sesion no encontrada"}), 404
        datos = dict(sess.ultimos_datos_mapa)
        if sess.symbiosis:
            try:
                status = sess.symbiosis.get_system_status()
                datos["gps_symbiosis"] = status
            except Exception:
                pass
        return jsonify(datos)

    @app.route('/api/gps/estado_completo')
    def gps_estado_completo():
        user_id = _get_user_id_from_request()
        sess = get_session(user_id)
        if not sess or not sess.symbiosis:
            return jsonify({"error": "GPS Symbiosis no disponible para esta sesion"}), 503
        try:
            status = sess.symbiosis.get_system_status()
            if sess.symbiosis.rl:
                status["rl"] = {
                    "step": sess.symbiosis.rl.step,
                    "weights": sess.symbiosis.rl.weights,
                    "performance": sess.symbiosis.rl.perf
                }
            if sess.symbiosis.gps.geofence:
                status["geofences_stats"] = sess.symbiosis.gps.geofence.get_statistics()
            return jsonify(status), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # MINING DEMO - HTML ESTATICO
    # ============================================================
    @app.route('/mining_demo')
    def mining_demo():
        return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UBER DAIMON VIVO + SOCIALCOIN + GPS</title>
<style>
:root { --bg-primary: #0f0f23; --bg-secondary: #1a1a2e; --text-primary: #00ff41; --text-secondary: #4d94ff; --accent-green: #00cc44; --pro-gold: #ffd700; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: var(--bg-primary); color: var(--text-primary); min-height: 100vh; line-height: 1.5; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
header { text-align: center; padding: 20px 0; border-bottom: 2px solid var(--text-primary); margin-bottom: 25px; }
h1 { font-size: 2.5rem; text-shadow: 0 0 10px var(--text-primary); margin-bottom: 8px; }
.dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 25px; }
.panel { background: rgba(20,20,40,0.7); padding: 20px; border-radius: 12px; border: 1px solid var(--text-secondary); }
.stats-bar { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 15px; }
.stat-item { text-align: center; padding: 10px; background: rgba(0,20,40,0.5); border-radius: 8px; border: 1px solid var(--accent-green); }
.stat-value { font-weight: bold; font-size: 1.4rem; display: block; }
.stat-label { font-size: 0.85rem; color: var(--text-secondary); }
.uber-status { display: flex; align-items: center; padding: 10px; background: rgba(0,30,20,0.5); border-radius: 8px; margin-bottom: 15px; }
.uber-status-indicator { width: 14px; height: 14px; border-radius: 50%; margin-right: 12px; background-color: var(--text-secondary); }
.input-group { margin: 15px 0; }
.input-group label { display: block; margin-bottom: 6px; color: var(--text-secondary); }
.input-group input { width: 100%; padding: 12px; background: rgba(10,20,40,0.8); border: 1px solid var(--text-primary); border-radius: 8px; color: var(--text-primary); }
.btn { background: linear-gradient(135deg, var(--accent-green), #00ff55); color: #001a09; border: none; padding: 14px; font-size: 1rem; font-weight: bold; border-radius: 30px; cursor: pointer; width: 100%; margin: 8px 0; }
.btn-uber { background: linear-gradient(135deg, #1a1a2e, var(--text-secondary)); color: white; border: 2px solid var(--text-secondary); }
.btn-gps { background: linear-gradient(135deg, #1a5c3a, #1ee588); color: white; border: 2px solid #1ee588; }
.pro-badge { display: inline-block; background: var(--pro-gold); color: black; font-weight: bold; padding: 2px 8px; border-radius: 20px; margin-left: 10px; font-size: 0.7rem; }
.log-container { background: rgba(10,10,30,0.9); border: 2px solid var(--text-primary); height: 350px; overflow-y: auto; padding: 15px; border-radius: 10px; font-family: monospace; font-size: 0.9rem; grid-column: 1 / -1; }
.log-entry { margin-bottom: 10px; padding: 8px; background: rgba(30,30,60,0.5); border-radius: 5px; border-left: 3px solid var(--text-secondary); }
.log-entry .timestamp { color: var(--text-secondary); margin-right: 8px; }
.log-entry .pro { color: var(--pro-gold); }
.gps-status { background: rgba(0,40,20,0.5); padding: 10px; border-radius: 8px; margin: 10px 0; font-size: 0.85rem; }
</style>
</head>
<body>
<div class="container">
<header><h1>UBER DAIMON VIVO + SOCIALCOIN + GPS</h1><p>Sistema Autonomo de IA + Mineria Social + GPS Symbiosis</p></header>
<div class="dashboard">
<div class="panel"><h3>Estadisticas</h3><div class="stats-bar"><div class="stat-item"><span class="stat-value" id="blockCount">0</span><span class="stat-label">Bloques</span></div><div class="stat-item"><span class="stat-value" id="rewardCount">0.00</span><span class="stat-label">UBER COINS</span></div></div><div class="uber-status"><div class="uber-status-indicator"></div><span>Conductor: <strong id="conductorEstado">IDLE</strong></span><span id="proBadgeHeader" style="display:none;" class="pro-badge">PRO</span></div><div class="gps-status" id="gpsStatus">GPS Symbiosis: Verificando...</div></div>
<div class="panel"><h3>Configuracion</h3><div class="input-group"><label>Usuario:</label><input type="text" id="userInput" value="conductor_codigo"></div><div class="input-group"><label>URL:</label><input type="text" id="videoUrl" placeholder="https://..."></div><button class="btn" onclick="startMining()">Mineria Social</button><button class="btn btn-uber" id="mejorOpcionBtnDashboard" onclick="activarMejorOpcionDashboard()">MEJOR OPCION</button><button class="btn btn-gps" onclick="checkGPSStatus()">GPS STATUS</button></div>
<div class="log-container" id="logContainer"><h3>Consola</h3></div>
</div>
</div>
<script>
(function() {
var storageKey = 'taxi_user_id';
var userId = localStorage.getItem(storageKey);
if (!userId) {
userId = 'user_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
localStorage.setItem(storageKey, userId);
}
window.USER_ID = userId;
var originalFetch = window.fetch;
window.fetch = function(url, options) {
options = options || {};
options.headers = options.headers || {};
options.headers['X-User-ID'] = window.USER_ID;
return originalFetch(url, options);
};
})();
function sTF(val,d){d=d||2;var n=parseFloat(val);return(typeof n==='number'&&isFinite(n))?n.toFixed(d):'0.'+'0'.repeat(d)}
function playBeep(){try{var a=new(window.AudioContext||window.webkitAudioContext)();var o=a.createOscillator();var g=a.createGain();o.connect(g);g.connect(a.destination);o.type='sine';o.frequency.value=1200;g.gain.value=0.4;o.start();o.stop(a.currentTime+0.18)}catch(e){}}
function playRoarWithVoice(){try{var a=new(window.AudioContext||window.webkitAudioContext)();var o=a.createOscillator();var g=a.createGain();o.connect(g);g.connect(a.destination);o.type='sawtooth';o.frequency.value=60;g.gain.value=0.35;o.start();g.gain.exponentialRampToValueAtTime(0.001,a.currentTime+1.4);o.stop(a.currentTime+1.4)}catch(e){}if('speechSynthesis' in window){speechSynthesis.cancel();var u=new SpeechSynthesisUtterance('Protocolo activado');u.lang='es-ES';u.rate=0.9;speechSynthesis.speak(u)}}
function addLog(msg,type){type=type||'info';var c=document.getElementById('logContainer');if(!c)return;var d=document.createElement('div');d.className='log-entry';d.innerHTML='<span class="timestamp">['+new Date().toLocaleTimeString()+']</span> '+msg;c.appendChild(d);c.scrollTop=c.scrollHeight}
function activarMejorOpcionDashboard(){var btn=document.getElementById('mejorOpcionBtnDashboard');btn.disabled=true;playBeep();addLog('BEEP...','info');setTimeout(function(){playRoarWithVoice();addLog('Protocolo activado.','info');btn.textContent='Activando...';fetch(location.origin+'/uber/activar_mejor_opcion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({imprimir_prompt:true})}).then(function(res){return res.json()}).then(function(d){if(d.message){addLog('OK '+d.message,'pro');document.getElementById('proBadgeHeader').style.display='inline-block';document.getElementById('conductorEstado').textContent=d.estado||'MEJOR_OPCION'}}).catch(function(e){addLog('Error: '+e.message,'error')}).finally(function(){btn.disabled=false;btn.textContent='MEJOR OPCION'})},2000)}
function startMining(){var url=document.getElementById('videoUrl').value;var user=document.getElementById('userInput').value;addLog('Iniciando mineria...','info');fetch(location.origin+'/api/v1/miner',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,user:user})}).then(function(res){return res.json()}).then(function(d){addLog('Bloqueo: +'+sTF(d&&d.reward)+' UBER MONEDAS','pro');document.getElementById('blockCount').innerText=(parseInt(document.getElementById('blockCount').innerText)||0)+1;document.getElementById('rewardCount').innerText=sTF(d&&d.reward)}).catch(function(e){addLog('Error: '+e.message,'error')})}
function checkGPSStatus(){fetch(location.origin+'/api/gps/estado_completo').then(function(res){return res.json()}).then(function(d){var el=document.getElementById('gpsStatus');if(d.location&&d.location.latitude){el.innerHTML='GPS: ONLINE | Lat:'+d.location.latitude.toFixed(4)+' Lon:'+d.location.longitude.toFixed(4)+' | Vel:'+d.location.speed_kmh.toFixed(1)+' km/h | RL:'+(d.rl?d.rl.step:0);el.style.color='#00ff6b'}else{el.innerHTML='GPS: OFFLINE';el.style.color='#ff4466'}addLog('GPS Status: '+(d.location&&d.location.latitude?'ONLINE':'OFFLINE'),'info')}).catch(function(){document.getElementById('gpsStatus').innerHTML='GPS: ERROR';addLog('GPS Status: ERROR','error')})}
function updateStats(){fetch(location.origin+'/health').then(function(res){return res.json()}).then(function(d){document.getElementById('blockCount').innerText=d.blocks_mined||0;document.getElementById('rewardCount').innerText=sTF(d.uber_coins);if(d.gps_symbiosis&&d.gps_symbiosis.location){var el=document.getElementById('gpsStatus');el.innerHTML='GPS: ONLINE | RL Step:'+(d.gps_symbiosis.rl_step||0);el.style.color='#00ff6b'}}).catch(function(){})}
setInterval(updateStats,3000);updateStats();checkGPSStatus();if('speechSynthesis' in window)speechSynthesis.getVoices();
</script>
</body>
</html>"""

    # ============================================================
    # EXPORTACIONES Y FUNCIONES AUXILIARES
    # ============================================================
    __all__ = ['app', 'HTTP_PORT', 'log', 'get_recent_logs',
               'minar_bloque_por_publicacion_controlado', 'obtener_estado_completo',
               'symbiosis', 'gps_registry']

    def obtener_estado_completo(usuario_id: str) -> Dict[str, Any]:
        sess = get_session(usuario_id)
        if not sess:
            return {"error": "Sesion no encontrada"}
        estado: Dict[str, Any] = {
            "modulo": "parte8_frontend_html_integrado",
            "version": "6.0+gps_symbiosis_multiuser",
            "puerto": HTTP_PORT,
            "estado_conductor": sess.estado_conductor,
            "zona_actual": sess.ultima_zona,
            "uber_coins": sess.uber_coins.to_float() if hasattr(sess.uber_coins, 'to_float') else 0.0,
            "bloques_minados": len(sess.blockchain),
            "ceoia_disponible": ceoia is not None,
            "gps_symbiosis_disponible": sess.symbiosis is not None,
            "timestamp": time.time()
        }
        if sess.symbiosis:
            try:
                estado["gps_symbiosis_status"] = sess.symbiosis.get_system_status()
            except Exception:
                pass
        return estado

    def iniciar_frontend_hilo():
        def _run():
            try:
                app.run(host="0.0.0.0", port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)
            except OSError as e:
                if "Address already in use" in str(e):
                    log_message(f"Puerto {HTTP_PORT} ya en uso")
                else:
                    log_message(f"Error al iniciar la interfaz: {e}")
        hilo = threading.Thread(target=_run, daemon=True, name="FrontendFlask")
        hilo.start()
        log_message(f"Frontend iniciado en hilo (puerto {HTTP_PORT})")
        return hilo

    def iniciar_limpieza_sesiones():
        def limpiar():
            while True:
                time.sleep(3600)
                cleanup_old_sessions()
        hilo = threading.Thread(target=limpiar, daemon=True, name="SessionCleaner")
        hilo.start()
        log_message("Limpieza de sesiones iniciada (cada 1 hora)")

else:
    # Si Flask no está disponible, mostramos un warning
    log.warning("Flask no disponible. La interfaz web no funcionara.")
    # Definimos funciones dummy para evitar errores en otras partes
    def iniciar_frontend_hilo():
        log.error("Flask no instalado. No se puede iniciar el frontend.")
        return None

    def iniciar_limpieza_sesiones():
        return None

# ================================================================================
# SECCION 31: MAIN UNIFICADO (Flask en hilo + modo continuo GPS)
# ================================================================================

def iniciar_limpieza_sesiones_seguro():
    if HAS_FLASK:
        return iniciar_limpieza_sesiones()
    log.warning("Limpieza de sesiones deshabilitada (Flask no disponible)")
    return None


def iniciar_frontend_hilo_seguro():
    if HAS_FLASK:
        return iniciar_frontend_hilo()
    log.warning("Frontend deshabilitado (Flask no disponible)")
    return None


def ejecutar_modo_continuo() -> None:
    print("\n" + "=" * 70)
    print(" SISTEMA GPS SYMBIOSIS ULTRA v3.0 - MODO CONTINUO")
    print("=" * 70)
    print("  Modulos activos:")
    print("  - GPS con EKF mejorado")
    print("  - DGPS (Correccion Diferencial)")
    print("  - IMU (Fusion Inercial)")
    print("  - Bluetooth (Kalman RSSI + Fingerprinting)")
    print("  - WiFi Positioning")
    print("  - Telefonia Celular (LTE/GSM)")
    print("  - Geofencing")
    print("  - Enrutamiento (Dijkstra/A*)")
    print("  - RL Ensemble (DQN/SARSA/AC/PPO)")
    print("  - Fuzzy Logic")
    print("  - Auto-aprendizaje de Beacons, Torres y WiFi")
    print("  - Uber Bridge (sensores nativos Android)")
    print("=" * 70)
    print("  Presiona Ctrl+C para detener")
    print("=" * 70)

    user_session = UserSession("default_user")
    symb = SymbiosisGPS(user_session, use_real_gps=True, allow_sim=True)
    symb.enable_bluetooth_auto_learning(True)
    symb.enable_cellular_auto_learning(True)
    symb.enable_wifi_auto_learning(True)

    # --- BLOQUE: INTEGRACION UBER BRIDGE ---
    if UBER_BRIDGE_AVAILABLE:
        try:
            if auto_integrate_uber_bridge(symb):
                log.info("GPS Symbiosis usando sensores nativos Android (Uber Bridge)")
            else:
                log.info("GPS Symbiosis usando termux-api (fallback)")
        except Exception as e:
            log.warning("Error en integracion Uber Bridge: {}".format(e))

    print("\n[+] Auto-aprendizaje activado:")
    print("  - Bluetooth: ACTIVADO")
    print("  - Celular: ACTIVADO")
    print("  - WiFi: ACTIVADO")
    if UBER_BRIDGE_AVAILABLE and getattr(symb.gps, '_uber_bridge', None) and symb.gps._uber_bridge.is_available():
        print("  - Uber Bridge: ACTIVADO (sensores nativos Android)")

    print("\n[+] Esperando primera fijacion GPS (max 60s)...")
    print("    Consejo: Sal al exterior o acerca a una ventana para mejor senal")
    first_fix = None
    intentos = 0
    while first_fix is None and intentos < 60:
        first_fix = symb.get_location()
        if first_fix:
            print("\n[OK] Primera fijacion obtenida en {}s!".format(intentos))
            break
        if intentos % 10 == 0 and intentos > 0:
            print("  ... {}s esperando (proveedor: GPS/Network)".format(intentos))
        print(".", end="", flush=True)
        time.sleep(1)
        intentos += 1

    if first_fix:
        print("[+] Primera fijacion: ({:.6f}, {:.6f}) prec={:.1f}m".format(
            first_fix.latitude, first_fix.longitude, first_fix.accuracy))
        symb.add_geofence(first_fix.latitude, first_fix.longitude, 0.5, "base")
        print("[+] Geocerca 'base' creada en ubicacion actual (radio 500m)")
        print("[+] Iniciando aprendizaje inicial de fuentes...")
        if hasattr(symb.gps, 'force_learning'):
            results = symb.gps.force_learning()
            print("  Aprendizaje inicial: BT={}, CELL={}, WiFi={}".format(
                results.get('bluetooth', 0),
                results.get('cellular', 0),
                results.get('wifi', 0)))
    else:
        print("\n[!] Sin fijacion GPS tras 60s. Continuando en modo simulado...")

    print("\n" + "=" * 70)
    print(" SISTEMA ACTIVO - MONITOREANDO UBICACION Y APRENDIENDO")
    print("=" * 70)

    cycle_count = 0
    start_time = time.time()
    last_log_time = start_time
    last_location = None
    update_interval = 1.0
    log_interval = 20
    learning_interval = 60
    last_learning_time = start_time
    running = True

    def signal_handler(sig: int, frame: Any) -> None:
        nonlocal running
        print("\n[!] Senal de interrupcion recibida. Apagando sistema...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while running:
            cycle_start = time.time()
            cycle_count += 1
            location = symb.get_location()

            if location:
                speed = symb.gps.get_speed()
                kf_quality = symb.gps.kalman.get_quality() if symb.gps.kalman else 1.0
                radar = compute_wifi_radar(symb.gps.last_wifi_networks)
                radar_compact = format_radar_compact(radar)

                if cycle_count % 5 == 0:
                    print("[{:06d}] LAT:{:10.6f} LON:{:10.6f} ACC:{:5.1f}m SRC:{:12} SPD:{:5.1f}km/h KF:{:.2f}".format(
                        cycle_count, location.latitude, location.longitude,
                        location.accuracy, location.source, speed, kf_quality))
                    print("  RADAR: {}".format(radar_compact))

                if last_location:
                    active_before = symb.gps.geofence.get_active_fences(last_location)
                    active_now = symb.gps.geofence.get_active_fences(location)
                    entered = set(f.id for f in active_now) - set(f.id for f in active_before)
                    exited = set(f.id for f in active_before) - set(f.id for f in active_now)
                    for fid in entered:
                        print("  [GEOFENCE] ENTRADA a '{}'".format(fid))
                    for fid in exited:
                        print("  [GEOFENCE] SALIDA de '{}'".format(fid))
                last_location = location
            else:
                if cycle_count % 5 == 0:
                    print("[{:06d}] Buscando senal GPS...".format(cycle_count))

            now = time.time()

            if now - last_learning_time >= learning_interval:
                if hasattr(symb.gps, 'force_learning'):
                    results = symb.gps.force_learning()
                    total_learned = sum(results.values())
                    if total_learned > 0:
                        print("  [APRENDIZAJE] +{} nuevas fuentes (BT:{}, CELL:{}, WiFi:{})".format(
                            total_learned,
                            results.get('bluetooth', 0),
                            results.get('cellular', 0),
                            results.get('wifi', 0)))
                last_learning_time = now

            if now - last_log_time >= log_interval:
                stats = symb.get_system_status()
                gps_stats = stats.get('gps_stats', {})
                learning_stats = {}
                if hasattr(symb.gps, 'get_learning_stats'):
                    learning_stats = symb.gps.get_learning_stats()
                uptime = now - start_time
                print("\n" + "-" * 70)
                print(" [ESTADISTICAS] Uptime: {:.1f}min | Ciclos: {}".format(
                    uptime / 60, cycle_count))
                print(" [SENSORES] GPS: {} | BT: {} | WiFi: {} | Cell: {}".format(
                    gps_stats.get('gps_updates', 0),
                    gps_stats.get('bt_updates', 0),
                    gps_stats.get('wifi_updates', 0),
                    gps_stats.get('cellular_updates', 0)))
                print(" [CALIDAD] Kalman: {:.2f} | DGPS: {}".format(
                    gps_stats.get('kalman_quality', 0),
                    gps_stats.get('dgps_stats', {}).get('corrections_applied', 0)))
                print(" [APRENDIZAJE] Beacons: {} | Torres: {} | WiFi: {}".format(
                    learning_stats.get('bluetooth', {}).get('known_beacons', 0),
                    learning_stats.get('cellular', {}).get('known_towers', 0),
                    learning_stats.get('wifi', {}).get('known_networks', 0)))
                print(" [TRAYECTORIA] Puntos: {} | Distancia: {:.1f}m".format(
                    gps_stats.get('trajectory_points', 0),
                    gps_stats.get('total_distance_m', 0)))
                if UBER_BRIDGE_AVAILABLE and hasattr(symb.gps, '_uber_bridge'):
                    bridge = symb.gps._uber_bridge
                    if bridge and bridge.is_available():
                        bridge_stats = bridge.get_stats()
                        print(" [UBER BRIDGE] Disponible | Calls: {} | Rate: {:.1f}%".format(
                            bridge_stats.get('calls', 0),
                            bridge_stats.get('success_rate', 0)))
                print("-" * 70)
                last_log_time = now

            elapsed = time.time() - cycle_start
            sleep_time = max(0, update_interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[!] Interrupcion por usuario")
    except Exception as e:
        print("\n[!] Error inesperado: {}".format(e))
        traceback.print_exc()
    finally:
        print("\n" + "=" * 70)
        print(" APAGANDO SISTEMA - GUARDANDO DATOS...")
        print("=" * 70)
        elapsed_time = time.time() - start_time
        status = symb.get_system_status()
        gps_stats = status.get('gps_stats', {})
        learning_stats = {}
        if hasattr(symb.gps, 'get_learning_stats'):
            learning_stats = symb.gps.get_learning_stats()
        print("  Tiempo de ejecucion: {:.0f} segundos ({:.1f} minutos)".format(
            elapsed_time, elapsed_time / 60))
        print("  Ciclos completados: {}".format(cycle_count))
        print("  Actualizaciones GPS: {}".format(gps_stats.get('gps_updates', 0)))
        print("  Actualizaciones BT: {}".format(gps_stats.get('bt_updates', 0)))
        print("  Actualizaciones WiFi: {}".format(gps_stats.get('wifi_updates', 0)))
        print("  Puntos en trayectoria: {}".format(gps_stats.get('trajectory_points', 0)))
        print("  Distancia total: {:.1f}m".format(gps_stats.get('total_distance_m', 0)))
        print("")
        print("  [RESUMEN APRENDIZAJE]")
        print("  Beacons conocidos: {}".format(
            learning_stats.get('bluetooth', {}).get('known_beacons', 0)))
        print("  Torres conocidas: {}".format(
            learning_stats.get('cellular', {}).get('known_towers', 0)))
        print("  Redes WiFi conocidas: {}".format(
            learning_stats.get('wifi', {}).get('known_networks', 0)))
        print("  Estaciones DGPS: {}".format(
            learning_stats.get('dgps', {}).get('stations', 0)))
        symb.shutdown()
        print("\n[+] Sistema apagado correctamente.")
        print("=" * 70)


def mostrar_ayuda() -> None:
    print("""
======================================================================
                GPS SYMBIOSIS ULTRA - AYUDA
======================================================================

  COMANDOS DISPONIBLES:

  1. Modo Continuo (por defecto)
     Ejecuta el sistema en modo CLI con monitoreo continuo

  2. Modo Web (si Flask esta disponible)
     Accede a: http://localhost:8080/puente
     Accede a: http://localhost:8080/mining_demo

  3. Auto-aprendizaje automatico
     - Bluetooth: Escanea y aprende beacons cercanos
     - Celular: Aprende torres LTE/GSM
     - WiFi: Aprende redes WiFi cercanas

  4. Uber Bridge (sensores nativos Android)
     Si UberBridgeService.java esta corriendo en el puerto
     9877, el sistema usara GPS, BLE, WiFi y celular
     nativos de Android. Fallback automatico a termux-api.

  5. Persistencia de datos
     Los datos aprendidos se guardan en:
     ./gps_learned_data.json

  6. Teclas durante ejecucion:
     Ctrl+C  - Detener el sistema

======================================================================
""")


if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("UBER DAIMON VIVO + SOCIALCOIN + GPS SYMBIOSIS (UNIFICADO) v3.0", flush=True)
    print("=" * 70, flush=True)
    if HAS_FLASK:
        print("Puerto Flask: {}".format(HTTP_PORT), flush=True)
        print("Mapa Pro: http://localhost:{}/puente".format(HTTP_PORT), flush=True)
        print("Mining Demo: http://localhost:{}/mining_demo".format(HTTP_PORT), flush=True)
    else:
        print("Flask NO disponible. Solo modo CLI activo.", flush=True)
    print("Auto-aprendizaje: ACTIVADO (Beacons, Torres, WiFi)", flush=True)
    print("Persistencia de datos: ACTIVADA (gps_learned_data.json)", flush=True)
    if UBER_BRIDGE_AVAILABLE:
        print("Uber Bridge: DETECTADO (sensores nativos Android disponibles)", flush=True)
    else:
        print("Uber Bridge: NO DETECTADO (usando termux-api como fallback)", flush=True)
    print("=" * 70, flush=True)

    Path(__file__).parent.joinpath('static').mkdir(exist_ok=True)

    if HAS_FLASK:
        iniciar_limpieza_sesiones_seguro()
        hilo_frontend = iniciar_frontend_hilo_seguro()
        if hilo_frontend:
            print("[+] Frontend Flask corriendo en hilo daemon", flush=True)
            print("[+] Accede al mapa en: http://localhost:{}/puente".format(HTTP_PORT), flush=True)
        else:
            print("[!] No se pudo iniciar el frontend Flask", flush=True)

    mostrar_ayuda()
    ejecutar_modo_continuo()
    
