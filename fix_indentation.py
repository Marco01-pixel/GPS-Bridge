#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_indentation.py
Corrige la indentacion de apk_gps_bridge.py con backup automatico.
Version mejorada: maneja decoradores, strings multi-linea y comentarios.
"""

import re
import shutil
from pathlib import Path
from datetime import datetime


def fix_indentation(archivo_entrada: Path, archivo_salida: Path) -> bool:
    """Aplica indentacion correcta al archivo."""
    try:
        contenido = archivo_entrada.read_text(encoding='utf-8')
        lineas = contenido.split('\n')
        lineas_corregidas = []
        
        indent_level = 0
        indent_size = 4
        in_multiline_string = False
        multiline_quote = None
        
        # Palabras clave que inician bloque (aumentan indentacion)
        inicio_bloque = [
            'class ', 'def ', 'if ', 'elif ', 'else:', 'for ', 'while ',
            'try:', 'except ', 'except:', 'finally:', 'with ', 'async def ',
            'async for ', 'async with '
        ]
        
        # Palabras clave que cierran bloque (disminuyen indentacion)
        fin_bloque = ['elif ', 'else:', 'except ', 'except:', 'finally:']
        
        for i, linea in enumerate(lineas):
            linea_stripped = linea.strip()
            
            # Detectar strings multi-linea (""" o ''')
            if not in_multiline_string:
                if '"""' in linea_stripped or "'''" in linea_stripped:
                    quote = '"""' if '"""' in linea_stripped else "'''"
                    count = linea_stripped.count(quote)
                    if count == 1:
                        in_multiline_string = True
                        multiline_quote = quote
            
            # Si estamos dentro de un string multi-linea, preservar tal cual
            if in_multiline_string:
                lineas_corregidas.append(linea)
                if multiline_quote in linea_stripped:
                    count = linea_stripped.count(multiline_quote)
                    if count == 1 or (count == 2 and not linea_stripped.startswith(multiline_quote)):
                        in_multiline_string = False
                        multiline_quote = None
                continue
            
            # Lineas vacias
            if not linea_stripped:
                lineas_corregidas.append('')
                continue
            
            # Decoradores (@app.route, @staticmethod, etc) - mismo nivel que la funcion
            if linea_stripped.startswith('@'):
                indent = ' ' * (indent_level * indent_size)
                lineas_corregidas.append(indent + linea_stripped)
                continue
            
            # Comentarios al inicio de linea
            if linea_stripped.startswith('#'):
                indent = ' ' * (indent_level * indent_size)
                lineas_corregidas.append(indent + linea_stripped)
                continue
            
            # Detectar fin de bloque ANTES de aplicar indentacion
            # elif, else, except, finally van al mismo nivel que el if/try anterior
            if any(linea_stripped.startswith(kw) for kw in fin_bloque):
                indent_level = max(0, indent_level - 1)
            
            # Aplicar indentacion
            indent = ' ' * (indent_level * indent_size)
            lineas_corregidas.append(indent + linea_stripped)
            
            # Detectar inicio de bloque DESPUES de aplicar indentacion
            # Solo si la linea termina con : y no es parte de un string/dict
            if linea_stripped.endswith(':'):
                # Verificar que no sea un dict/lista o string
                es_bloque = any(linea_stripped.startswith(kw) for kw in inicio_bloque)
                if es_bloque:
                    indent_level += 1
        
        # Unir lineas
        contenido_corregido = '\n'.join(lineas_corregidas)
        
        # Guardar
        archivo_salida.write_text(contenido_corregido, encoding='utf-8')
        return True
    
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    entrada = Path('apk_gps_bridge.py')
    salida = Path('apk_gps_bridge_CORREGIDO.py')
    backup = Path(f'apk_gps_bridge.py.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    
    if not entrada.exists():
        print(f"[ERROR] No existe: {entrada}")
        print(f"[INFO] Busca el archivo en: ~/BridgeApp/GPS_Bridge/")
        return 1
    
    # Crear backup del original
    print(f"[INFO] Creando backup: {backup}")
    shutil.copy2(entrada, backup)
    print(f"[OK] Backup creado")
    
    print(f"[INFO] Corrigiendo indentacion...")
    if fix_indentation(entrada, salida):
        print(f"[OK] Archivo corregido: {salida}")
        
        # Verificar sintaxis
        import subprocess
        result = subprocess.run(
            ['python3', '-m', 'py_compile', str(salida)],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"[OK] Sintaxis valida")
            print(f"")
            print(f"[INFO] Para usar el archivo corregido:")
            print(f"  mv {salida} {entrada}")
            print(f"  python3 {entrada}")
            print(f"")
            print(f"[INFO] Para restaurar el original:")
            print(f"  cp {backup} {entrada}")
        else:
            print(f"[WARN] Errores de sintaxis detectados:")
            print(result.stderr)
            print(f"")
            print(f"[INFO] Revisa manualmente: {salida}")
        
        return 0
    else:
        print("[ERROR] No se pudo corregir el archivo")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
