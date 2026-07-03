#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uber Bridge Client - Conecta con el servicio Android UberBridge
"""

import socket
import json
import time
import threading
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from collections import deque

class UberBridgeClient:
    """Cliente para conectar con el servicio Android UberBridge en puerto 9877"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9877, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._available = None
        self._last_check = 0
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 2.0
        self._lock = threading.RLock()
        self._stats = {
            'calls': 0,
            'success': 0,
            'failures': 0,
            'last_error': None
        }

    def _send_command(self, command: str) -> Optional[str]:
        with self._lock:
            self._stats['calls'] += 1
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                sock.send((command + "\n").encode('utf-8'))
                response = sock.recv(8192).decode('utf-8')
                sock.close()
                self._stats['success'] += 1
                self._stats['last_error'] = None
                return response
            except Exception as e:
                self._stats['failures'] += 1
                self._stats['last_error'] = str(e)
                return None

    def is_available(self, force_check: bool = False) -> bool:
        now = time.time()
        if not force_check and self._available is not None and (now - self._last_check) < 10:
            return self._available
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((self.host, self.port))
            sock.close()
            self._available = True
        except:
            self._available = False
        self._last_check = now
        return self._available

    def get_gps(self):
        if not self.is_available():
            return None
        now = time.time()
        with self._lock:
            if "gps" in self._cache and (now - self._cache_time.get("gps", 0)) < self._cache_ttl:
                return self._cache["gps"]
        response = self._send_command("GET_GPS")
        if response:
            try:
                data = json.loads(response)
                if "error" not in data:
                    coord = self._create_coordinate(
                        latitude=data.get('latitude', 0.0),
                        longitude=data.get('longitude', 0.0),
                        altitude=data.get('altitude', 0.0),
                        accuracy=data.get('accuracy', 10.0),
                        timestamp=data.get('timestamp', time.time()) / 1000.0,
                        source='android_gps'
                    )
                    with self._lock:
                        self._cache["gps"] = coord
                        self._cache_time["gps"] = now
                    return coord
            except:
                pass
        return None

    def _create_coordinate(self, latitude, longitude, altitude=0.0, accuracy=10.0, timestamp=None, source='android'):
        if timestamp is None:
            timestamp = time.time()
        @dataclass
        class Coord:
            latitude: float
            longitude: float
            altitude: float = 0.0
            accuracy: float = 0.0
            source: str = "unknown"
            timestamp: float = 0.0
            def is_valid(self):
                return (-90.0 <= self.latitude <= 90.0 and
                        -180.0 <= self.longitude <= 180.0 and
                        self.accuracy >= 0.0)
            def distance_to(self, other):
                import math
                lat1 = math.radians(self.latitude)
                lon1 = math.radians(self.longitude)
                lat2 = math.radians(other.latitude)
                lon2 = math.radians(other.longitude)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat * 0.5) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon * 0.5) ** 2
                return 6371.0 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            def distance_to_meters(self, other):
                return self.distance_to(other) * 1000.0
        return Coord(
            latitude=float(latitude),
            longitude=float(longitude),
            altitude=float(altitude),
            accuracy=float(accuracy),
            source=source,
            timestamp=float(timestamp) if timestamp else time.time()
        )

    def scan_bluetooth(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        now = time.time()
        cache_key = "bluetooth"
        with self._lock:
            if cache_key in self._cache and (now - self._cache_time.get(cache_key, 0)) < self._cache_ttl:
                return self._cache[cache_key]
        response = self._send_command("GET_BLUETOOTH")
        if response:
            try:
                data = json.loads(response)
                if "error" not in data:
                    devices = data.get('devices', [])
                    with self._lock:
                        self._cache[cache_key] = devices
                        self._cache_time[cache_key] = now
                    return devices
            except:
                pass
        return []

    def scan_wifi(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        now = time.time()
        cache_key = "wifi"
        with self._lock:
            if cache_key in self._cache and (now - self._cache_time.get(cache_key, 0)) < self._cache_ttl:
                return self._cache[cache_key]
        response = self._send_command("GET_WIFI")
        if response:
            try:
                data = json.loads(response)
                if "error" not in data:
                    networks = data.get('networks', [])
                    with self._lock:
                        self._cache[cache_key] = networks
                        self._cache_time[cache_key] = now
                    return networks
            except:
                pass
        return []

    def get_cell_info(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        now = time.time()
        cache_key = "cell"
        with self._lock:
            if cache_key in self._cache and (now - self._cache_time.get(cache_key, 0)) < self._cache_ttl:
                return self._cache[cache_key]
        response = self._send_command("GET_CELL")
        if response:
            try:
                data = json.loads(response)
                if "error" not in data:
                    cells = data.get('cells', [])
                    with self._lock:
                        self._cache[cache_key] = cells
                        self._cache_time[cache_key] = now
                    return cells
            except:
                pass
        return []

    def get_all(self) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None
        response = self._send_command("GET_ALL")
        if response:
            try:
                return json.loads(response)
            except:
                pass
        return None

    def ping(self) -> bool:
        response = self._send_command("PING")
        return response == "PONG"

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "available": self.is_available(),
                "host": self.host,
                "port": self.port,
                "cache_size": len(self._cache),
                "calls": self._stats['calls'],
                "success": self._stats['success'],
                "failures": self._stats['failures'],
                "success_rate": (self._stats['success'] / max(1, self._stats['calls'])) * 100,
                "last_error": self._stats['last_error']
            }

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_time.clear()


class PromptBLEBroadcaster:
    def __init__(self, bridge_client: Optional[UberBridgeClient] = None):
        self.bridge = bridge_client or UberBridgeClient()
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._listeners = []
    
    def start_broadcasting(self, interval: float = 5.0) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._broadcast_loop, daemon=True, args=(interval,))
        self._thread.start()
    
    def stop_broadcasting(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def _broadcast_loop(self, interval: float) -> None:
        while not self._stop_event.is_set():
            if self.bridge.is_available():
                gps = self.bridge.get_gps()
                if gps:
                    for listener in self._listeners:
                        try:
                            listener(gps)
                        except:
                            pass
            time.sleep(interval)
    
    def add_listener(self, callback: callable) -> None:
        self._listeners.append(callback)
    
    def remove_listener(self, callback: callable) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)


def apply_all_patches(system_instance) -> bool:
    bridge = UberBridgeClient()
    if not bridge.is_available():
        return False
    return True


if __name__ == "__main__":
    client = UberBridgeClient()
    print(f"Disponible? {client.is_available()}")
    if client.is_available():
        print("GPS:", client.get_gps())
        print("BT:", len(client.scan_bluetooth()))
        print("WiFi:", len(client.scan_wifi()))
        print("Cell:", len(client.get_cell_info()))
        print("Stats:", client.get_stats())
    else:
        print("Servicio no disponible. Ejecuta la APK primero.")
