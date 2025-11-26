import time
import threading
from datetime import datetime, timedelta
from supabase import create_client, Client
import platform
from os import system
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Literal

# ==============================
# CONFIG SUPABASE
# ==============================
SUPABASE_URL = "https://sklnwhmaapcmdnfeijzi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNrbG53aG1hYXBjbWRuZmVpanppIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg3MTMyNTAsImV4cCI6MjA3NDI4OTI1MH0.Rkj55NXXRa8Gc3TeZS6uXoFlskrRhU5pw3i8nI68Frs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

WEEKDAY_MAP = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# ==============================
# ESTADO DO LED (agora com 4 MODOS)
# ==============================
estado_led = {"valor": "off"}
estado_lock = threading.Lock()

# ==============================
# UTILITÁRIAS
# ==============================
def clear_terminal():
    system("cls") if platform.system() == "Windows" else system("clear")

def get_alarms():
    try:
        response = supabase.table("alarms").select("*").eq("enabled", True).execute()
        return response.data or []
    except Exception as e:
        print("[ERRO] ao buscar alarmes no Supabase:", e)
        return []

# ==============================
# LÓGICA DO ALARME
# ==============================
def set_estado(valor: str):
    if valor not in ("short", "long", "repeat", "off"):
        return False
    with estado_lock:
        estado_led["valor"] = valor
    print("[ESTADO] LED ->", valor)
    return True

def trigger_alarm(label: str, alarm_time: str, mode: str):
    print("\n" + "=" * 50)
    print(f"🔥 ALERTA! '{label}' disparou às {alarm_time} (modo: {mode})")
    print("=" * 50 + "\n")

    set_estado(mode)
    time.sleep(10)
    set_estado("off")

def check_alarms_loop(poll_seconds: int = 5):
    print("🔥 THREAD RODANDO: monitor de alarmes iniciado!")
    while True:
        try:
            print("\n⏳ Buscando alarmes no banco...")
            alarms = get_alarms()
            print("📦 Alarmes ativos:", alarms)

            now_utc = datetime.utcnow()
            now_utc_str = now_utc.strftime("%H:%M")
            weekday = WEEKDAY_MAP[now_utc.weekday()]

            now_br = now_utc - timedelta(hours=3)
            now_br_str = now_br.strftime("%H:%M")

            print("🕒 Hora UTC:", now_utc_str, "| BR:", now_br_str, "| dia:", weekday)

            for alarm in alarms:
                alarm_time_br = alarm.get("time")
                mode = alarm.get("mode", "off").lower()
                days = alarm.get("days") or WEEKDAY_MAP
                label = alarm.get("label") or "sem nome"

                h, m = alarm_time_br.split(":")
                h_utc = (int(h) + 3) % 24
                alarm_time_utc = f"{h_utc:02d}:{m}"

                print(f"⏰ Comparando agora {now_utc_str} com alarme {alarm_time_utc} | modo {mode}")

                if weekday in days and alarm_time_utc == now_utc_str:
                    trigger_alarm(label, alarm_time_br, mode)

        except Exception as e:
            print("[ERRO] no loop:", e)

        time.sleep(poll_seconds)

# ==============================
# API FASTAPI
# ==============================
app = FastAPI()

class EstadoRequest(BaseModel):
    valor: Literal["short", "long", "repeat", "off"]

@app.get("/")
def home():
    return {"mensagem": "API de alarmes rodando — use /estado-led"}

@app.get("/estado-led")
def get_estado():
    with estado_lock:
        return {"led": estado_led["valor"]}

@app.post("/estado-led")
def post_modo(req: EstadoRequest):
    ok = set_estado(req.valor)
    if not ok:
        return {"erro": "modo inválido"}
    return {"mensagem": "modo atualizado", "novo_estado": req.valor}

# ==============================
# INICIA THREAD NO STARTUP
# ==============================
@app.on_event("startup")
def start_thread():
    print("🚀 Iniciando monitor em background...")
    threading.Thread(target=check_alarms_loop, daemon=True).start()
