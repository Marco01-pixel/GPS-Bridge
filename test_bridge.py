#!/usr/bin/env python3
import socket
import json

def test_connection():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(('127.0.0.1', 9877))
        
        print("📡 Conectado al servicio Android")
        print("📤 Enviando: GET_GPS")
        s.send(b"GET_GPS\n")
        data = s.recv(4096).decode()
        s.close()
        
        print("📥 Respuesta:")
        print(json.dumps(json.loads(data), indent=2))
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_connection()
