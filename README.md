La forma más económica y simple para México es integrar el bot directo con WhatsApp Business Cloud API y ejecutarlo dentro del mismo servicio de tu ERP en Django en Railway (una sola instancia/contendedor). Lo ideal es portar el webhook del bot a una app de Django y aprovechar tu misma BD y despliegue.

Opciones

- Integración nativa en Django (recomendado): crear una app “whatsappbot” con endpoints, lógica de conversación y modelos. Corre con el mismo Gunicorn/Uvicorn de tu ERP en Railway.
- Monorepo con dos servicios en Railway: más limpio a nivel microservicio, pero ya no es la “misma instancia”; suele implicar costos separados.
- Mezclar Flask dentro del mismo contenedor: posible, pero innecesario y más frágil. Mejor unificar en Django.
Recomendación

- Migrar el webhook a Django y usar WhatsApp Cloud API. Ahorras el fee del proveedor y compartes infraestructura (procesos, BD, variables, logs) con el ERP en Railway.
Pasos en tu proyecto Django

- Crear app: whatsappbot
- Variables de entorno en Railway:
  - WHATSAPP_TOKEN
  - PHONE_NUMBER_ID
  - VERIFY_TOKEN
  - OPEN_HOUR, CLOSE_HOUR, SLOT_MINUTES, MAX_DAYS_AHEAD
- Modelos o persistencia:
  - Usa tu Postgres ya configurado en el ERP. Define Appointment (y opcionalmente una tabla para sesiones) o usa cache/Redis para sesiones.
- URLs:
  - GET /meta/webhook (verificación con VERIFY_TOKEN)
  - POST /meta/webhook (recepción de mensajes)
- Lógica:
  - Reutiliza el flujo que ya tenemos: “menu”, reservar, consultar, cancelar.
  - Enviar respuestas con requests a la Cloud API.
Ejemplo de implementación en Django

models.py (persistencia básica de citas)

```
from django.db import models

class Appointment(models.Model):
    STATUS_CHOICES = [
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
    ]
    code = models.CharField
    (max_length=16, unique=True)
    user_phone = models.CharField
    (max_length=32, db_index=True)
    name = models.CharField
    (max_length=128)
    start_at = models.DateTimeField()
    status = models.CharField
    (max_length=16, 
    choices=STATUS_CHOICES, 
    default="confirmed")

    def __str__(self):
        return f"{self.code} {self.
        user_phone} {self.start_at} {self.
        status}"
```
views.py (verificación y webhook; envía mensajes por Cloud API)

```
import os
import json
from datetime import datetime, date, 
time, timedelta
import requests
from django.http import HttpResponse, 
JsonResponse
from django.views.decorators.csrf import 
csrf_exempt
from django.utils.timezone import 
make_aware
from .models import Appointment

OPEN_HOUR = int(os.getenv("OPEN_HOUR", 
"9"))
CLOSE_HOUR = int(os.getenv("CLOSE_HOUR", 
"17"))
SLOT_MINUTES = int(os.getenv
("SLOT_MINUTES", "60"))
MAX_DAYS_AHEAD = int(os.getenv
("MAX_DAYS_AHEAD", "30"))

WHATSAPP_TOKEN = os.getenv
("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv
("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", 
"")
API_VERSION = os.getenv
("WHATSAPP_API_VERSION", "v17.0")

SESSIONS = {}

def menu_text():
    return (
        "👋 Hola, soy el asistente de 
        citas de la clínica.\n"
        "Responde con:\n"
        "1. Nueva cita\n"
        "2. Consultar mis citas\n"
        "3. Cancelar una cita\n"
        "Escribe 'menu' para volver al 
        inicio."
    )

def load_taken(d):
    qs = Appointment.objects.filter
    (status="confirmed", start_at__date=d)
    return {(a.start_at.strftime
    ("%H:%M")) for a in qs}

def next_slots_for_date(d: date):
    if d.weekday() > 4:
        return []
    cur = datetime.combine(d, time
    (OPEN_HOUR, 0))
    end = datetime.combine(d, time
    (CLOSE_HOUR, 0))
    slots = []
    while cur < end:
        slots.append(cur.strftime
        ("%H:%M"))
        cur += timedelta
        (minutes=SLOT_MINUTES)
    taken = load_taken(d)
    return [s for s in slots if s not in 
    taken]

def handle_message(session_key: str, 
body: str) -> str:
    text = body.strip().lower()
    sess = SESSIONS.get(session_key, 
    {"state": "menu"})
    if text in {"menu", "inicio", "hola", 
    "hi", "start"}:
        SESSIONS[session_key] = {"state": 
        "menu"}
        return menu_text()

    state = sess.get("state", "menu")
    if state == "menu":
        if text in {"1", "nueva", "nueva 
        cita", "reservar", "nuevo"}:
            sess.update({"state": 
            "ask_name", "booking": {}})
            SESSIONS[session_key] = sess
            return "Perfecto. ¿Cuál es tu 
            nombre completo?"
        if text in {"2", "consultar", 
        "mis citas"}:
            appts = Appointment.objects.
            filter
            (user_phone=session_key, 
            status="confirmed").order_by
            ("start_at")
            if not appts:
                return "No encuentro 
                citas activas para tu 
                número. Escribe 'menu' 
                para volver."
            lines = ["Tus citas 
            confirmadas:"]
            for a in appts:
                lines.append(f"- {a.
                start_at.strftime
                ('%Y-%m-%d %H:%M')} • 
                código {a.code}")
            return "\n".join(lines)
        if text in {"3", "cancelar", 
        "cancelar cita"}:
            sess.update({"state": 
            "cancel_ask_code"})
            SESSIONS[session_key] = sess
            return "Por favor, envía el 
            código de la cita a cancelar."
        return "No entendí tu respuesta.
        \n" + menu_text()

    if state == "ask_name":
        sess["booking"]["name"] = body.
        strip()
        sess["state"] = "ask_date"
        SESSIONS[session_key] = sess
        return "Gracias. ¿Para qué fecha 
        deseas tu cita? Formato: 
        AAAA-MM-DD"

    if state == "ask_date":
        try:
            d = datetime.strptime(body.
            strip(), "%Y-%m-%d").date()
        except ValueError:
            return "Formato de fecha no 
            válido. Usa AAAA-MM-DD (ej. 
            2026-03-20)."
        if d < date.today():
            return "La fecha ya pasó. 
            Elige una fecha futura."
        if d > (date.today() + timedelta
        (days=MAX_DAYS_AHEAD)):
            return f"Solo agendamos con 
            {MAX_DAYS_AHEAD} días de 
            anticipación."
        slots = next_slots_for_date(d)
        if not slots:
            return "No hay disponibilidad 
            para esa fecha (o es fin de 
            semana). Prueba otra fecha."
        sess["booking"]["date"] = d.
        strftime("%Y-%m-%d")
        sess["booking"]["slots"] = slots
        sess["state"] = "ask_time"
        SESSIONS[session_key] = sess
        return "Disponibilidad:\n" + ", ".
        join(slots) + "\nElige una hora 
        (HH:MM)."

    if state == "ask_time":
        hm = body.strip()
        slots = sess["booking"].get
        ("slots", [])
        if hm not in slots:
            return "Esa hora no está 
            disponible. Elige una de la 
            lista enviada (HH:MM)."
        sess["booking"]["time"] = hm
        sess["state"] = "confirm"
        SESSIONS[session_key] = sess
        name = sess["booking"]["name"]
        d = sess["booking"]["date"]
        return f"Confirma tu 
        cita:\nNombre: {name}\nFecha: {d}
        \nHora: {hm}\nResponde 'sí' para 
        confirmar o 'no' para cancelar."

    if state == "confirm":
        if text in {"si", "sí", "s", 
        "yes", "ok"}:
            d = datetime.strptime(sess
            ["booking"]["date"], 
            "%Y-%m-%d").date()
            hm = sess["booking"]["time"]
            start_dt = make_aware
            (datetime.combine(d, datetime.
            strptime(hm, "%H:%M").time()))
            code = str(Appointment.
            objects.count() + 1).zfill(5)
            Appointment.objects.create(
                code=code,
                user_phone=session_key,
                name=sess["booking"]
                ["name"],
                start_at=start_dt,
                status="confirmed",
            )
            SESSIONS[session_key] = 
            {"state": "menu"}
            return f"¡Listo! Tu cita 
            quedó para {d} a las {hm}. 
            Código: {code}\n{menu_text()}"
        else:
            SESSIONS[session_key] = 
            {"state": "menu"}
            return "Se canceló el proceso 
            de reserva.\n" + menu_text()

    if state == "cancel_ask_code":
        code = body.strip()
        try:
            a = Appointment.objects.get
            (code=code, 
            user_phone=session_key, 
            status="confirmed")
            a.status = "cancelled"
            a.save(update_fields=
            ["status"])
            SESSIONS[session_key] = 
            {"state": "menu"}
            return f"Cita {code} 
            cancelada.\n" + menu_text()
        except Appointment.DoesNotExist:
            return "No encontré una cita 
            activa con ese código para tu 
            número. Intenta de nuevo o 
            escribe 'menu'."

    SESSIONS[session_key] = {"state": 
    "menu"}
    return "No entendí tu respuesta.\n" + 
    menu_text()

def send_meta_message(to_number: str, 
text: str):
    if not (WHATSAPP_TOKEN and 
    PHONE_NUMBER_ID):
        return
    url = f"https://graph.facebook.com/
    {API_VERSION}/{PHONE_NUMBER_ID}/
    messages"
    headers = {"Authorization": f"Bearer 
    {WHATSAPP_TOKEN}", "Content-Type": 
    "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.lstrip("+"),
        "type": "text",
        "text": {"body": text},
    }
    try:
        requests.post(url, 
        headers=headers, json=payload, 
        timeout=10)
    except Exception:
        pass

def meta_verify(request):
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.
    verify_token")
    challenge = request.GET.get("hub.
    challenge")
    if mode == "subscribe" and token == 
    VERIFY_TOKEN:
        return HttpResponse(challenge or 
        "", status=200)
    return HttpResponse("Forbidden", 
    status=403)

@csrf_exempt
def meta_webhook(request):
    if request.method == "POST":
        data = json.loads(request.body.
        decode("utf-8") or "{}")
        for entry in data.get("entry", [])
        :
            for change in entry.get
            ("changes", []):
                value = change.get
                ("value", {})
                for m in value.get
                ("messages", []):
                    if m.get("type") == 
                    "text":
                        from_raw = m.get
                        ("from", "")
                        body = m.get
                        ("text", {}).get
                        ("body", "")
                        session_key = 
                        f"whatsapp:
                        +{from_raw}"
                        reply = 
                        handle_message
                        (session_key, 
                        body)
                        if from_raw:
                            send_meta_mess
                            age(from_raw, 
                            reply)
        return HttpResponse
        ("EVENT_RECEIVED", status=200)
    return HttpResponse(status=405)
```
urls.py (de la app)

```
from django.urls import path
from . import views

urlpatterns = [
    path("meta/webhook", views.
    meta_webhook),
    path("meta/webhook/", views.
    meta_webhook),  # por si Meta agrega 
    slash
    path("meta/verify", views.
    meta_verify),
    path("meta/verify/", views.
    meta_verify),
]
```
settings.py

- Añade la app a INSTALLED_APPS.
- Usa tus variables en Railway Variables.
- Si usas zona horaria, configura TIME_ZONE y USE_TZ=True.
Migraciones y arranque

```
python manage.py makemigrations 
whatsappbot
python manage.py migrate
# Railway: usa tu start command habitual 
(gunicorn o uvicorn-gunicorn) del ERP
```
Railway

- No necesitas nuevo servicio si lo integras en el mismo proyecto de Django.
- Solo agrega las variables en el mismo servicio (WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN, etc.).
- Después del deploy, configura en Meta:
  - Verificación (GET): https:// <tu-dominio-railway>/meta/verify usando VERIFY_TOKEN.</tu-dominio-railway>
  - Callback (POST): https:// <tu-dominio-railway>/meta/webhook y suscribe “messages”.</tu-dominio-railway>
Buenas prácticas

- Mueve SESSIONS a Redis/Cache (django-redis) para que el estado de conversación persista entre réplicas.
- Protege tokens en variables de entorno, nunca en el repo.
- Usa plantillas aprobadas de WhatsApp cuando inicies conversaciones (marketing/autenticación) para optimizar costos.
