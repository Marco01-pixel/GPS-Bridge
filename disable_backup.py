#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para desactivar TODAS las funciones de backup/persistencia automática
en 'sistema_uber_unificado_CONSOLIDADO.py'.
Comenta las llamadas a _save_all() y save_rl_model() que guardan datos en disco.
"""

import os
import re
import shutil
from datetime import datetime

ARCHIVO_ORIGINAL = "sistema_uber_unificado_CONSOLIDADO.py"
BACKUP_SUFIJO = ".backup_antes_de_desactivar_backup"
PATCHEADO_SUFIJO = ".patched"

# Patrones de búsqueda (expresiones regulares)
PATRONES = [
    # Llamada a _save_all() dentro de shutdown()
    {
        "buscar": r"(\s*)self\._save_all\s*\(\s*\)",
        "descripcion": "self._save_all() en shutdown()"
    },
    # Llamada a save_rl_model() en el endpoint /api/v1/miner
    {
        "buscar": r"(\s*)sess\.symbiosis\.save_rl_model\s*\(\s*\)",
        "descripcion": "sess.symbiosis.save_rl_model() en endpoint miner"
    },
    # Llamada a save_rl_model() dentro de algún otro método (por si acaso)
    {
        "buscar": r"(\s*)self\.save_rl_model\s*\(\s*\)",
        "descripcion": "self.save_rl_model() (genérico)"
    }
]

def aplicar_parches(contenido):
    """Aplica los parches al contenido del archivo, comentando las líneas que coinciden."""
    lineas = contenido.splitlines(keepends=True)
    nuevas_lineas = []
    cambios = 0

    for linea in lineas:
        modificada = False
        for patron in PATRONES:
            match = re.match(patron["buscar"], linea)
            if match:
                indent = match.group(1) or ""
                # Si la línea ya está comentada, no hacer nada
                if linea.lstrip().startswith("#"):
                    continue
                # Reemplazar por línea comentada
                nueva = f"{indent}# {linea.lstrip()}"
                nuevas_lineas.append(nueva)
                cambios += 1
                modificada = True
                print(f"   ✓ Comentada: {patron['descripcion']}")
                break
        if not modificada:
            nuevas_lineas.append(linea)

    return "".join(nuevas_lineas), cambios

def main():
    if not os.path.exists(ARCHIVO_ORIGINAL):
        print(f"❌ Error: No se encuentra el archivo '{ARCHIVO_ORIGINAL}'")
        return

    # Crear backup
    backup_nombre = ARCHIVO_ORIGINAL + BACKUP_SUFIJO
    print(f"📁 Creando backup en '{backup_nombre}'...")
    shutil.copy2(ARCHIVO_ORIGINAL, backup_nombre)

    # Leer contenido original
    with open(ARCHIVO_ORIGINAL, 'r', encoding='utf-8') as f:
        contenido = f.read()

    print("🔍 Aplicando parches...")
    nuevo_contenido, cambios = aplicar_parches(contenido)

    if cambios == 0:
        print("ℹ️  No se encontraron líneas que comentar. El archivo no fue modificado.")
        # Eliminar el backup porque no hubo cambios
        os.remove(backup_nombre)
        return

    # Guardar archivo parcheado
    patched_nombre = ARCHIVO_ORIGINAL + PATCHEADO_SUFIJO
    with open(patched_nombre, 'w', encoding='utf-8') as f:
        f.write(nuevo_contenido)
    print(f"✅ Archivo parcheado guardado como '{patched_nombre}'")

    # Preguntar si sobrescribir el original
    respuesta = input(f"\n¿Deseas reemplazar '{ARCHIVO_ORIGINAL}' con la versión parcheada? (s/N): ")
    if respuesta.lower() == 's':
        shutil.move(patched_nombre, ARCHIVO_ORIGINAL)
        print(f"✅ '{ARCHIVO_ORIGINAL}' ha sido actualizado con los parches.")
        print(f"📌 Backup original disponible en '{backup_nombre}'")
        print(f"📌 Para revertir, copia '{backup_nombre}' sobre '{ARCHIVO_ORIGINAL}'.")
    else:
        print(f"ℹ️  El archivo original no fue modificado.")
        print(f"   Puedes revisar el archivo parcheado en '{patched_nombre}'")
        print(f"   Si deseas aplicarlo manualmente, cópialo sobre el original.")

    print("\n✅ Proceso completado.")

if __name__ == "__main__":
    main()
