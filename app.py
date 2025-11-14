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
    print("🔥 THREAD RODANDO: check_alarms_loop começou de verdade!")
    while True:
        try:
            print("🔁 Loop ativo — verificando alarmes...")
            print("⏳ Buscando alarmes no Supabase...")
            alarms = get_alarms()
            print("📦 Alarmes recebidos:", alarms)

            # horário local do servidor (UTC no Render)
            now_utc = datetime.utcnow()
            now_utc_str = now_utc.strftime("%H:%M")
            weekday = WEEKDAY_MAP[now_utc.weekday()]

            print("🕒 Horário UTC do servidor:", now_utc_str)

            for alarm in alarms:
                alarm_time_br = alarm.get("time")    # ex: "16:50"
                
                # converter horário BR -> UTC (-3 horas)
                h, m = alarm_time_br.split(":")
                h = (int(h) + 3) % 24   # BR -> UTC
                alarm_time_utc = f"{h:02d}:{m}"

                print(f"🕒 Alarme (BR): {alarm_time_br} → (UTC): {alarm_time_utc}")

                days = alarm.get("days") or WEEKDAY_MAP

                if weekday in days:
                    if alarm_time_utc == now_utc_str:
                        trigger_alarm(
                            alarm.get("label") or f"Alarme {alarm_time_br}",
                            alarm_time_br,
                            alarm.get("mode") or "short"
                        )

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


