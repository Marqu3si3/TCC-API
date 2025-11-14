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
# ESTADO DO LED
# ==============================
estado_led = {"valor": "nao"}
estado_lock = threading.Lock()


# ==============================
# UTILITÁRIAS
# ==============================
def clear_terminal():
    if platform.system() == "Windows":
        system("cls")
    else:
        system("clear")


def get_alarms():
    try:
        response = supabase.table("alarms").select("*").eq("enabled", True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[ERRO] ao buscar alarmes no supabase: {e}")
        return []


# ==============================
# LÓGICA DO ALARME
# ==============================
def set_estado(valor: str):
    if valor not in ("sim", "nao"):
        return False
    with estado_lock:
        estado_led["valor"] = valor
    print(f"[ESTADO] led -> {valor}")
    return True


def trigger_alarm(label, alarm_time, mode):
    print("\n" + "=" * 50)
    print(f"🔥 ALERTA! Alarme '{label}' disparou ({alarm_time})")
    print("=" * 50 + "\n")

    set_estado("sim")
    time.sleep(10)
    set_estado("nao")


def check_alarms_loop(poll_seconds: int = 5):
    print("🔥 THREAD RODANDO DE VERDADE!")
    while True:
        print("🔁 Loop ativo — verificando alarmes...")
        alarms = get_alarms()
        print("📦 Alarmes recebidos:", alarms)

        try:
            now = datetime.now()
            now_str = now.strftime("%H:%M")
            today = WEEKDAY_MAP[now.weekday()]

            for alarm in alarms:
                alarm_time = alarm.get("time")
                label = alarm.get("label") or f"Alarme {alarm_time}"
                days = alarm.get("days") or WEEKDAY_MAP

                if today not in days:
                    continue

                # ==============================
                # SOLUÇÃO 1 — intervalo de disparo de 60 segundos
                # ==============================
                alarm_dt = datetime.strptime(alarm_time, "%H:%M")
                alarm_dt = now.replace(hour=alarm_dt.hour, minute=alarm_dt.minute, second=0, microsecond=0)

                window_start = alarm_dt
                window_end = alarm_dt + timedelta(seconds=59)

                if window_start <= now <= window_end:
                    trigger_alarm(label, alarm_time, alarm.get("mode"))
        except Exception as e:
            print(f"[ERRO] no loop de alarmes: {e}")

        time.sleep(poll_seconds)


# ==============================
# API FASTAPI
# ==============================
app = FastAPI()


class EstadoRequest(BaseModel):
    valor: Literal["sim", "nao"]


@app.get("/")
def home():
    return {"mensagem": "API de alarmes integrada com Supabase — responda /estado-led (sim/nao)"}


@app.get("/estado-led")
def get_estado_led():
    with estado_lock:
        return {"led": estado_led["valor"]}


@app.post("/estado-led")
def post_estado_led(req: EstadoRequest):
    ok = set_estado(req.valor)
    if not ok:
        return {"erro": "valor inválido"}
    return {"mensagem": "estado atualizado", "novo_estado": req.valor}


@app.get("/ligar")
def ligar():
    set_estado("sim")
    return {"mensagem": "LED setado para sim"}


@app.get("/desligar")
def desligar():
    set_estado("nao")
    return {"mensagem": "LED setado para nao"}


# ==============================
# THREAD DE FUNDO
# ==============================
def start_background_thread():
    t = threading.Thread(target=check_alarms_loop, args=(5,), daemon=True)
    t.start()


@app.on_event("startup")
def start_thread():
    print("🚀 Iniciando thread de monitoramento...")
    start_background_thread()
