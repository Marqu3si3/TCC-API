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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNrbG53aG1hYXBjbWRuZmVpanppIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg3MTMyNTAsImV4cCI6MjA3NDI4OTI1MH0.Rkj55NXXRa8Gc3TeZS6uXoFlskrRhU5pw3i8nI68Frs"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

WEEKDAY_MAP = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# ==============================
# ESTADO DO LED (para o ESP consultar)
# ==============================
# valor: "sim" ou "nao"
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
    """Busca todos os alarmes ativos do banco."""
    try:
        response = supabase.table("alarms").select("*").eq("enabled", True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[ERRO] ao buscar alarmes no supabase: {e}")
        return []


# ==============================
# LÓGICA DO ALARME (sem serial)
# ==============================
def set_estado(valor: str):
    """Seta o estado do LED de forma thread-safe ("sim" ou "nao")."""
    if valor not in ("sim", "nao"):
        return False
    with estado_lock:
        estado_led["valor"] = valor
    print(f"[ESTADO] led -> {valor}")
    return True


def trigger_alarm(label, alarm_time, mode):
    """Executa ações quando o alarme dispara: setar 'sim' por 10s e voltar."""
    print("\n" + "=" * 50)
    print(f"🔥 ALERTA! Alarme '{label}' disparou ({alarm_time})")
    print("=" * 50 + "\n")

    # acende (API passa a responder "sim")
    set_estado("sim")

    # duração do alerta (pode ajustar)
    time.sleep(10)

    # volta ao estado "nao"
    set_estado("nao")


def check_alarms_loop(poll_seconds: int = 5):
    """Thread separada que verifica os alarmes sem travar a API."""
    print("⏰ Thread de monitoramento iniciada...")
    while True:
        try:
            now = datetime.now()
            now_str = now.strftime("%H:%M")
            today = WEEKDAY_MAP[now.weekday()]

            alarms = get_alarms()

            for alarm in alarms:
                alarm_time = alarm.get("time")
                label = alarm.get("label") or f"Alarme {alarm_time}"
                mode = alarm.get("mode") or "short"
                days = alarm.get("days") or WEEKDAY_MAP

                if today in days:
                    if alarm_time == now_str:
                        # dispara sem bloquear a verificação de outros alarmes
                        # (trigger_alarm faz sleep(10) — já é rápido; se quiser paralelizar, criar threads por alarme)
                        trigger_alarm(label, alarm_time, mode)
                # else: não toca hoje
        except Exception as e:
            print(f"[ERRO] no loop de alarmes: {e}")

        time.sleep(poll_seconds)


# ==============================
# API (FastAPI)
# ==============================
app = FastAPI()


class EstadoRequest(BaseModel):
    valor: Literal["sim", "nao"]


@app.get("/")
def home():
    return {"mensagem": "API de alarmes integrada com Supabase — responda /estado-led (sim/nao)"}


@app.get("/estado-led")
def get_estado_led():
    """Endpoint que o ESP32 consulta para saber se deve acender o LED."""
    with estado_lock:
        return {"led": estado_led["valor"]}


@app.post("/estado-led")
def post_estado_led(req: EstadoRequest):
    """Atualiza manualmente o estado do LED (útil para testes)."""
    ok = set_estado(req.valor)
    if not ok:
        return {"erro": "valor inválido, use 'sim' ou 'nao'"}
    return {"mensagem": "estado atualizado", "novo_estado": req.valor}


# endpoints auxiliares para ligar/desligar via GET (opcional)
@app.get("/ligar")
def ligar():
    set_estado("sim")
    return {"mensagem": "LED setado para sim"}


@app.get("/desligar")
def desligar():
    set_estado("nao")
    return {"mensagem": "LED setado para nao"}


# ==============================
# START: thread de alarmes + uvicorn
# ==============================
def start_background_thread():
    t = threading.Thread(target=check_alarms_loop, args=(5,), daemon=True)
    t.start()


if __name__ == "__main__":
    start_background_thread()
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=10000)
