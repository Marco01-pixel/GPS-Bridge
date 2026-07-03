#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_autoload.py
Hace que la APK cargue la pagina web automaticamente al abrirse.
- Arregla cleartext traffic
- Modifica el Activity para auto-cargar WebView
- Recompila la APK
"""

import sys
import re
import shutil
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()
BACKUP_DIR = PROJECT_ROOT / "_backups_autoload"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TARGET_URL = "http://localhost:8080/puente"


def log(msg: str, tipo: str = "INFO") -> None:
    colores = {"OK": "\033[92m", "WARN": "\033[93m", "ERR": "\033[91m", "INFO": "\033[94m"}
    color = colores.get(tipo, "")
    print(f"{color}[{tipo}]\033[0m {msg}")


def backup(ruta: Path) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    destino = BACKUP_DIR / f"{ruta.name}.{TIMESTAMP}.bak"
    shutil.copy2(ruta, destino)
    log(f"Backup: {destino}", "OK")


def encontrar_activity() -> list[Path]:
    """Encuentra los archivos Activity del proyecto."""
    candidatos = []
    for ext in ("*.java", "*.kt"):
        for p in PROJECT_ROOT.rglob(f"app/src/main/**/{ext}"):
            if "/build/" not in str(p):
                candidatos.append(p)
    return candidatos


def fix_cleartext(manifest: Path) -> bool:
    """Agrega usesCleartextTraffic al manifest."""
    try:
        contenido = manifest.read_text(encoding="utf-8")
    except Exception as e:
        log(f"Error leyendo manifest: {e}", "ERR")
        return False
    
    if "usesCleartextTraffic" in contenido:
        log("usesCleartextTraffic ya existe", "OK")
        return True
    
    patron = re.compile(r"(<application\b[^>]*)(>)", re.DOTALL)
    match = patron.search(contenido)
    if not match:
        log("No se encontro <application>", "ERR")
        return False
    
    apertura = match.group(1)
    sep = "" if apertura.endswith((" ", "\n")) else " "
    nuevo = f"{apertura}{sep}android:usesCleartextTraffic=\"true\">{match.group(2)[1:]}"
    
    nuevo_contenido = contenido[:match.start()] + nuevo + contenido[match.end():]
    backup(manifest)
    manifest.write_text(nuevo_contenido, encoding="utf-8")
    log("Agregado usesCleartextTraffic al manifest", "OK")
    return True


def modificar_activity_autoload(activity: Path) -> bool:
    """Modifica el Activity para auto-cargar la URL en onCreate."""
    try:
        contenido = activity.read_text(encoding="utf-8")
    except Exception as e:
        log(f"Error leyendo {activity}: {e}", "ERR")
        return False
    
    es_kotlin = activity.suffix == ".kt"
    
    # Verificar si ya tiene auto-load
    if TARGET_URL in contenido:
        log(f"{activity.name} ya tiene auto-load configurado", "OK")
        return True
    
    # Buscar onCreate
    if "onCreate" not in contenido:
        log(f"{activity.name} no tiene onCreate()", "ERR")
        return False
    
    # Buscar WebView
    if "WebView" not in contenido:
        log(f"{activity.name} no usa WebView", "WARN")
        return False
    
    # Insertar codigo de auto-load despues de setContentView
    patron_setcontent = re.compile(r"(setContentView\s*\([^)]+\)\s*;?)", re.DOTALL)
    match = patron_setcontent.search(contenido)
    
    if not match:
        log("No se encontro setContentView", "ERR")
        return False
    
    # Codigo a insertar
    if es_kotlin:
        codigo_insertar = f"""

        // === AUTO-LOAD WebView ===
        val webView = findViewById<WebView>(R.id.webview)
        webView.settings.apply {{
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
        }}
        webView.loadUrl("{TARGET_URL}")
        // === FIN AUTO-LOAD ===
"""
    else:
        codigo_insertar = f"""

        // === AUTO-LOAD WebView ===
        WebView webView = findViewById(R.id.webview);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        webView.loadUrl("{TARGET_URL}");
        // === FIN AUTO-LOAD ===
"""
    
    # Insertar despues de setContentView
    insert_pos = match.end()
    nuevo_contenido = contenido[:insert_pos] + codigo_insertar + contenido[insert_pos:]
    
    backup(activity)
    activity.write_text(nuevo_contenido, encoding="utf-8")
    log(f"Modificado {activity.name} para auto-load", "OK")
    return True


def rebuild() -> bool:
    """Recompila la APK."""
    import subprocess
    gradlew = PROJECT_ROOT / "gradlew"
    if not gradlew.exists():
        log("gradlew no encontrado", "ERR")
        return False
    
    gradlew.chmod(0o755)
    log("Recompilando APK...", "INFO")
    
    try:
        r = subprocess.run(
            ["./gradlew", "clean", "assembleDebug"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if r.returncode == 0:
            apk = PROJECT_ROOT / "app/build/outputs/apk/debug/app-debug.apk"
            if apk.exists():
                log(f"APK generada: {apk}", "OK")
                return True
        else:
            log("Build fallo", "ERR")
            print(r.stdout[-1000:])
            print(r.stderr[-1000:])
            return False
    except Exception as e:
        log(f"Error en build: {e}", "ERR")
        return False


def main() -> int:
    log("=== AUTO-LOAD FIX ===", "INFO")
    
    # 1. Encontrar manifest
    manifests = list(PROJECT_ROOT.rglob("app/src/main/AndroidManifest.xml"))
    if not manifests:
        log("No se encontro AndroidManifest.xml", "ERR")
        return 1
    
    # 2. Fix cleartext
    fix_cleartext(manifests[0])
    
    # 3. Encontrar y modificar Activity
    activities = encontrar_activity()
    if not activities:
        log("No se encontraron archivos Activity", "ERR")
        return 1
    
    log(f"Encontrados {len(activities)} archivo(s) de codigo", "INFO")
    
    modificados = 0
    for act in activities:
        if modificar_activity_autoload(act):
            modificados += 1
    
    if modificados == 0:
        log("No se pudo modificar ningun Activity automaticamente", "WARN")
        log("Revisa manualmente el Activity principal", "WARN")
        return 1
    
    # 4. Recompilar
    if not rebuild():
        return 1
    
    log("Proceso completado", "OK")
    log(f"Backups en: {BACKUP_DIR}", "INFO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
