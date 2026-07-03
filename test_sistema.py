#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_sistema.py
Diagnostico completo de UBER DAIMON + GPS SYMBIOSIS.
Prueba cada componente y muestra tabla de estado.
"""

import sys
import os
import json
import socket
import subprocess
import time
from pathlib import Path
from datetime import datetime

# ================================================================================
# SECCION 1: CONFIGURACION
# ================================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
PUERTO_FLASK = 8080
PUERTO_BRIDGE = 9877
TIMEOUT = 3  # segundos por prueba

# Colores terminal
class C:
    OK = "\033[92m"
    WARN = "\033[93m"
    ERR = "\033[91m"
    INFO = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"
    GRAY = "\033[90m"


# ================================================================================
# SECCION 2: UTILIDADES
# ================================================================================

def log(msg: str, tipo: str = "INFO") -> None:
    colores = {"OK": C.OK, "WARN": C.WARN, "ERR": C.ERR, "INFO": C.INFO}
    print(f"{colores.get(tipo, '')}[{tipo}]{C.END} {msg}")


def ejecutar(cmd: list[str], timeout: int = TIMEOUT) -> tuple[int, str]:
    """Ejecuta comando y retorna (returncode, output)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=PROJECT_ROOT
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except FileNotFoundError:
        return -2, "COMANDO NO ENCONTRADO"
    except Exception as e:
        return -3, str(e)


def puerto_abierto(puerto: int, host: str = "127.0.0.1") -> bool:
    """Verifica si un puerto TCP esta escuchando."""
    try:
        with socket.create_connection((host, puerto), timeout=2):
            return True
    except Exception:
        return False


def http_get(url: str, timeout: int = TIMEOUT) -> tuple[bool, int, str]:
    """Hace GET simple con socket (sin requests)."""
    try:
        from urllib.request import urlopen, Request
        from urllib.error import URLError, HTTPError
        req = Request(url, headers={"User-Agent": "TestSistema/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return True, resp.status, f"{len(resp.read())} bytes"
    except HTTPError as e:
        return False, e.code, str(e)
    except URLError as e:
        return False, 0, str(e.reason)
    except Exception as e:
        return False, 0, str(e)


# ================================================================================
# SECCION 3: TESTS
# ================================================================================

class TestRunner:
    def __init__(self):
        self.resultados = []
    
    def agregar(self, categoria: str, nombre: str, estado: bool, detalle: str = "") -> None:
        self.resultados.append({
            "categoria": categoria,
            "nombre": nombre,
            "estado": estado,
            "detalle": detalle
        })
    
    def imprimir(self) -> None:
        print(f"\n{C.BOLD}{'='*78}{C.END}")
        print(f"{C.BOLD}  REPORTE DE DIAGNOSTICO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.END}")
        print(f"{C.BOLD}{'='*78}{C.END}\n")
        
        # Agrupar por categoria
        categorias = {}
        for r in self.resultados:
            categorias.setdefault(r["categoria"], []).append(r)
        
        total_ok = sum(1 for r in self.resultados if r["estado"])
        total_fail = len(self.resultados) - total_ok
        
        for cat, tests in categorias.items():
            print(f"{C.BOLD}{C.INFO}  [{cat}]{C.END}")
            for t in tests:
                icono = f"{C.OK}✓{C.END}" if t["estado"] else f"{C.ERR}✗{C.END}"
                estado_txt = f"{C.OK}OK{C.END}" if t["estado"] else f"{C.ERR}FALLO{C.END}"
                detalle = f" {C.GRAY}({t['detalle']}){C.END}" if t["detalle"] else ""
                print(f"    {icono} {t['nombre']:<40} [{estado_txt}]{detalle}")
            print()
        
        # Resumen
        print(f"{C.BOLD}{'='*78}{C.END}")
        print(f"{C.BOLD}  RESUMEN:{C.END} ", end="")
        print(f"{C.OK}{total_ok} OK{C.END} / {C.ERR}{total_fail} FALLOS{C.END} / {len(self.resultados)} TOTAL")
        
        if total_fail == 0:
            print(f"\n  {C.OK}{C.BOLD}✓ SISTEMA OPERATIVO AL 100%{C.END}")
        elif total_ok > total_fail:
            print(f"\n  {C.WARN}{C.BOLD}⚠ SISTEMA OPERATIVO PARCIALMENTE{C.END}")
        else:
            print(f"\n  {C.ERR}{C.BOLD}✗ SISTEMA CON FALLAS CRITICAS{C.END}")
        print(f"{C.BOLD}{'='*78}{C.END}\n")


# ================================================================================
# SECCION 4: TESTS INDIVIDUALES
# ================================================================================

def test_entorno(runner: TestRunner) -> None:
    """Test de entorno Python y sistema."""
    cat = "ENTORNO"
    
    # Python version
    runner.agregar(cat, "Python >= 3.10",
                   sys.version_info >= (3, 10),
                   f"v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Termux
    es_termux = "com.termux" in os.environ.get("PREFIX", "")
    runner.agregar(cat, "Entorno Termux", es_termux,
                   os.environ.get("PREFIX", "no detectado"))
    
    # Directorio proyecto
    runner.agregar(cat, "Directorio proyecto",
                   PROJECT_ROOT.exists(),
                   str(PROJECT_ROOT))


def test_dependencias(runner: TestRunner) -> None:
    """Test de modulos Python requeridos."""
    cat = "DEPENDENCIAS PYTHON"
    
    modulos = [
        ("flask", "Flask (servidor web)"),
        ("numpy", "NumPy (calculos)"),
        ("json", "JSON (persistencia)"),
        ("socket", "Socket (red)"),
        ("threading", "Threading (concurrencia)"),
    ]
    
    for modulo, nombre in modulos:
        try:
            __import__(modulo)
            runner.agregar(cat, nombre, True, "importado")
        except ImportError:
            runner.agregar(cat, nombre, False, "NO INSTALADO")
    
    # Modulos opcionales
    opcionales = [
        ("scipy", "SciPy (EKF avanzado)"),
        ("requests", "Requests (HTTP cliente)"),
    ]
    for modulo, nombre in opcionales:
        try:
            __import__(modulo)
            runner.agregar(cat, nombre + " [opcional]", True, "importado")
        except ImportError:
            runner.agregar(cat, nombre + " [opcional]", False, "no instalado (opcional)")


def test_archivos_proyecto(runner: TestRunner) -> None:
    """Test de archivos criticos del proyecto."""
    cat = "ARCHIVOS PROYECTO"
    
    archivos = [
        ("sistema_uber_unificado.py", "Sistema principal"),
        ("uber_bridge_client.py", "Cliente Uber Bridge"),
        ("test_bridge.py", "Test bridge"),
        ("gps_learned_data.json", "Datos aprendidos"),
    ]
    
    for archivo, nombre in archivos:
        ruta = PROJECT_ROOT / archivo
        existe = ruta.exists()
        detalle = f"{ruta.stat().st_size} bytes" if existe else "NO ENCONTRADO"
        runner.agregar(cat, nombre, existe, detalle)
    
    # Directorios
    dirs = [
        ("static", "Static (HTML/CSS/JS)"),
        ("gps_symbiosis_data", "Datos Symbiosis"),
        ("app/src/main", "Codigo Android"),
    ]
    for d, nombre in dirs:
        ruta = PROJECT_ROOT / d
        runner.agregar(cat, nombre, ruta.exists(),
                       "existe" if ruta.exists() else "NO ENCONTRADO")


def test_puertos(runner: TestRunner) -> None:
    """Test de puertos de red."""
    cat = "PUERTOS DE RED"
    
    runner.agregar(cat, f"Flask puerto {PUERTO_FLASK}",
                   puerto_abierto(PUERTO_FLASK),
                   "escuchando" if puerto_abierto(PUERTO_FLASK) else "NO ACTIVO")
    
    runner.agregar(cat, f"Uber Bridge puerto {PUERTO_BRIDGE}",
                   puerto_abierto(PUERTO_BRIDGE),
                   "escuchando" if puerto_abierto(PUERTO_BRIDGE) else "NO ACTIVO")


def test_endpoints_http(runner: TestRunner) -> None:
    """Test de endpoints HTTP del servidor Flask."""
    cat = "ENDPOINTS HTTP"
    
    if not puerto_abierto(PUERTO_FLASK):
        runner.agregar(cat, "Servidor Flask", False, "puerto no activo - saltando tests")
        return
    
    runner.agregar(cat, "Servidor Flask", True, f"puerto {PUERTO_FLASK} activo")
    
    endpoints = [
        (f"http://localhost:{PUERTO_FLASK}/", "Raiz /"),
        (f"http://localhost:{PUERTO_FLASK}/mapa_pro", "Mapa Pro"),
        (f"http://localhost:{PUERTO_FLASK}/mining_demo", "Mining Demo"),
        (f"http://localhost:{PUERTO_FLASK}/api/status", "API Status"),
        (f"http://localhost:{PUERTO_FLASK}/api/gps", "API GPS"),
    ]
    
    for url, nombre in endpoints:
        ok, status, detalle = http_get(url)
        runner.agregar(cat, nombre, ok,
                       f"HTTP {status} - {detalle}" if ok else detalle)


def test_termux_api(runner: TestRunner) -> None:
    """Test de termux-api (sensores)."""
    cat = "TERMUX-API (SENSORES)"
    
    # Verificar que termux-api esta instalado
    rc, out = ejecutar(["which", "termux-location"], timeout=2)
    if rc != 0:
        runner.agregar(cat, "termux-api instalado", False,
                       "instalar con: pkg install termux-api")
        return
    
    runner.agregar(cat, "termux-api instalado", True, "binarios encontrados")
    
    # Probar cada sensor con timeout corto
    sensores = [
        ("termux-location -p gps", "GPS (satelite)"),
        ("termux-location -p network", "Location (red)"),
        ("termux-location -p last", "Last known location"),
        ("termux-wifi-connectioninfo", "WiFi info"),
        ("termux-wifi-scanresults", "WiFi scan"),
        ("termux-battery-status", "Bateria"),
        ("termux-telephony-deviceinfo", "Telefonia"),
    ]
    
    for cmd, nombre in sensores:
        rc, out = ejecutar(cmd.split(), timeout=5)
        if rc == 0 and out:
            # Intentar parsear JSON para verificar
            try:
                data = json.loads(out)
                runner.agregar(cat, nombre, True, f"OK ({len(out)} bytes)")
            except json.JSONDecodeError:
                runner.agregar(cat, nombre, True, "respuesta no-JSON")
        else:
            runner.agregar(cat, nombre, False, out[:60] if out else "sin respuesta")


def test_uber_bridge(runner: TestRunner) -> None:
    """Test de Uber Bridge (sensores nativos Android)."""
    cat = "UBER BRIDGE"
    
    if not puerto_abierto(PUERTO_BRIDGE):
        runner.agregar(cat, "Servidor Bridge", False,
                       f"puerto {PUERTO_BRIDGE} no activo")
        runner.agregar(cat, "Sensores nativos", False,
                       "Bridge no disponible")
        return
    
    runner.agregar(cat, "Servidor Bridge", True,
                   f"puerto {PUERTO_BRIDGE} activo")
    
    # Probar endpoints del bridge
    endpoints = [
        (f"http://localhost:{PUERTO_BRIDGE}/", "Raiz Bridge"),
        (f"http://localhost:{PUERTO_BRIDGE}/status", "Status Bridge"),
        (f"http://localhost:{PUERTO_BRIDGE}/sensors", "Sensores"),
    ]
    
    for url, nombre in endpoints:
        ok, status, detalle = http_get(url, timeout=2)
        runner.agregar(cat, nombre, ok,
                       f"HTTP {status}" if ok else detalle[:50])


def test_persistencia(runner: TestRunner) -> None:
    """Test de persistencia de datos."""
    cat = "PERSISTENCIA"
    
    archivo = PROJECT_ROOT / "gps_learned_data.json"
    
    if not archivo.exists():
        runner.agregar(cat, "Archivo de datos", False, "no existe aun")
        return
    
    try:
        contenido = archivo.read_text(encoding="utf-8")
        data = json.loads(contenido)
        runner.agregar(cat, "Archivo de datos", True,
                       f"{len(contenido)} bytes, JSON valido")
        
        # Ver secciones
        secciones = ["beacons", "torres", "wifi", "gps_history"]
        for sec in secciones:
            if sec in data:
                n = len(data[sec]) if isinstance(data[sec], (list, dict)) else 0
                runner.agregar(cat, f"  - {sec}", True, f"{n} registros")
            else:
                runner.agregar(cat, f"  - {sec}", False, "no existe")
    except json.JSONDecodeError as e:
        runner.agregar(cat, "Archivo de datos", False, f"JSON invalido: {e}")
    except Exception as e:
        runner.agregar(cat, "Archivo de datos", False, str(e))


def test_sintaxis_python(runner: TestRunner) -> None:
    """Test de sintaxis del archivo principal."""
    cat = "SINTAXIS PYTHON"
    
    archivo = PROJECT_ROOT / "sistema_uber_unificado.py"
    if not archivo.exists():
        runner.agregar(cat, "sistema_uber_unificado.py", False, "no existe")
        return
    
    rc, out = ejecutar([sys.executable, "-m", "py_compile", str(archivo)], timeout=10)
    runner.agregar(cat, "sistema_uber_unificado.py",
                   rc == 0,
                   "sintaxis OK" if rc == 0 else out[:80])
    
    # Tambien probar cliente bridge
    archivo2 = PROJECT_ROOT / "uber_bridge_client.py"
    if archivo2.exists():
        rc, out = ejecutar([sys.executable, "-m", "py_compile", str(archivo2)], timeout=10)
        runner.agregar(cat, "uber_bridge_client.py",
                       rc == 0,
                       "sintaxis OK" if rc == 0 else out[:80])


# ================================================================================
# SECCION 5: MAIN
# ================================================================================

def main() -> int:
    print(f"\n{C.BOLD}{'='*78}{C.END}")
    print(f"{C.BOLD}  UBER DAIMON + GPS SYMBIOSIS - DIAGNOSTICO COMPLETO{C.END}")
    print(f"{C.BOLD}{'='*78}{C.END}")
    print(f"  Iniciando tests... (puede tardar ~15 segundos)\n")
    
    runner = TestRunner()
    
    tests = [
        ("Entorno", test_entorno),
        ("Dependencias Python", test_dependencias),
        ("Archivos del proyecto", test_archivos_proyecto),
        ("Sintaxis Python", test_sintaxis_python),
        ("Puertos de red", test_puertos),
        ("Endpoints HTTP", test_endpoints_http),
        ("Termux-API", test_termux_api),
        ("Uber Bridge", test_uber_bridge),
        ("Persistencia", test_persistencia),
    ]
    
    for nombre, func in tests:
        print(f"  {C.INFO}→{C.END} Probando {nombre}...")
        try:
            func(runner)
        except Exception as e:
            runner.agregar(nombre, "Test completo", False, f"error: {e}")
    
    runner.imprimir()
    
    # Recomendaciones
    print(f"{C.BOLD}RECOMENDACIONES:{C.END}")
    fallos = [r for r in runner.resultados if not r["estado"]]
    
    if not fallos:
        print(f"  {C.OK}✓ No se requieren acciones{C.END}")
    else:
        for f in fallos:
            if "Flask" in f["nombre"] or "puerto 8080" in f["nombre"]:
                print(f"  {C.WARN}→{C.END} Inicia el servidor: python3 sistema_uber_unificado.py")
            elif "Bridge" in f["nombre"] and "puerto 9877" in f["nombre"]:
                print(f"  {C.WARN}→{C.END} Abre la APK GPS Bridge y pulsa INICIAR")
            elif "termux-api" in f["nombre"].lower():
                print(f"  {C.WARN}→{C.END} Instala termux-api: pkg install termux-api")
            elif "POST_NOTIFICATIONS" in f.get("detalle", ""):
                print(f"  {C.WARN}→{C.END} Acepta permisos en Ajustes de la APK")
    
    print()
    return 0 if not fallos else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{C.WARN}Diagnostico cancelado por el usuario{C.END}")
        sys.exit(130)
