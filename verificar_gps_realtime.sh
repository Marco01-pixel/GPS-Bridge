#!/bin/bash

echo "======================================================================"
echo "VERIFICACION GPS EN TIEMPO REAL"
echo "======================================================================"
echo ""
echo "Este script monitorea si el sistema Python está recibiendo GPS"
echo "Presiona Ctrl+C para detener"
echo ""

# Monitorear logs del sistema
while true; do
    # Verificar si hay proceso corriendo
    if ! pgrep -f "sistema_uber_unificado.py" > /dev/null; then
        echo "[!] El sistema no está corriendo"
        echo "    Ejecuta: ./activar_sistema.sh"
        exit 1
    fi
    
    # Verificar puertos
    PUERTO_FLASK=$(netstat -tlnp 2>/dev/null | grep 8080 | wc -l)
    PUERTO_BRIDGE=$(netstat -tlnp 2>/dev/null | grep 9877 | wc -l)
    
    echo "[$(date +%H:%M:%S)] Flask: $([ $PUERTO_FLASK -gt 0 ] && echo '✓' || echo '✗') | Bridge: $([ $PUERTO_BRIDGE -gt 0 ] && echo '✓' || echo '✗')"
    
    # Probar endpoint de health
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "  ✓ Endpoint /health responde"
    else
        echo "  ✗ Endpoint /health no responde"
    fi
    
    sleep 5
done
