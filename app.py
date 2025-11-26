import time
import threading
from datetime import datetime
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
SUPABASE_KEY = "SUA_CHAVE_AQUI"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
WEEKDAY_MAP = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# ==============================
# ESTADO DO LED
# ==============================
estado_led = {"valor": "nao"}
estado_lock = threading.Lock()

# ==============================
# FUNÇÕES
# ==============================
def clear_terminal():
    system("cls" if platform.system() == "Windows" else "clear")

def get_alarms():
    try:
        res = supabase.table("alarms").select("*").eq("enabled", True).execute()
        return res.data or []
    except Exception as e:
        print("[ERRO] buscar alarmes:", e)
        return []

def set_estado(valor: str):
    if valor not in ("curto", "longo", "repetido", "nao"):
        print("[ERRO] Estado inválido:", valor)
        return False
    with estado_lock:
        estado_led["valor"] = valor
    print("[ESTADO] led ->", valor)
    return True

# ==============================
# TIPOS DE DISPARO
# ==============================
def sinal_curto():
    set_estado("curto")
    time.sleep(2)
    set_estado("nao")

def sinal_longo():
    set_estado("longo")
    time.sleep(5)
    set_estado("nao")

def sinal_repetido():
    # 1 minuto alternando LED ON/OFF no site
    set_estado("repetido")
    inicio = time.time()
    while time.time() - inicio < 60:
        print("🔔 (repeat) batendo...")
        time.sleep(1)
    set_estado("nao")

# ==============================
# THREAD DE ALARMES
# ==============================
def check_alarms_loop(poll_seconds=5):
    print("🔥 THREAD DE ALARMES ONLINE!")
    while True:
        now = datetime.utcnow()
        now_str = now.strftime("%H:%M")
        weekday = WEEKDAY_MAP[now.weekday()]

        alarms = get_alarms()
        print("\n📦 Alarmes:", alarms)
        print("🕒 Agora (UTC):", now_str, "| Dia:", weekday)

        for a in alarms:
            t_br = a["time"]  # ex: "16:50"
            h, m = t_br.split(":")

            # converter BR (-3) → UTC
            h_utc = (int(h) + 3) % 24
            t_utc = f"{h_utc:02d}:{m}"

            print(f"⏰ Alarme {t_br} (BR) → {t_utc} (UTC)")
            
            if weekday in (a.get("days") or WEEKDAY_MAP):
                if t_utc == now_str:
                    print("🚨 BATEU NA HORA!")
                    mode = a.get("mode", "short")

                    if mode == "short":
                        sinal_curto()
                    elif mode == "long":
                        sinal_longo()
                    elif mode == "repeat":
                        sinal_repetido()

        time.sleep(poll_seconds)

# ==============================
# API FASTAPI
# ==============================
app = FastAPI()

class EstadoRequest(BaseModel):
    valor: Literal["curto", "longo", "repetido", "nao"]

@app.get("/")
def home():
    return {"mensagem": "Sistema de alarmes rodando"}

@app.get("/estado-led")
def get_estado_led():
    with estado_lock:
        return {"led": estado_led["valor"]}

@app.post("/estado-led")
def post_estado_led(req: EstadoRequest):
    ok = set_estado(req.valor)
    return {"ok": ok, "estado": req.valor}

# ==============================
# STARTUP
# ==============================
@app.on_event("startup")
def start_bg():
    threading.Thread(target=check_alarms_loop, daemon=True).start()
    print("🚀 Monitoramento iniciado!")
