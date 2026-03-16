# WhatsApp Chatbot para agendar citas clínicas (Django + Cloud API)

MVP listo para Railway: Django + Postgres con integración a WhatsApp Business Cloud API (recomendado para México por costo). Incluye endpoints de webhook, modelo de citas y healthcheck.

## Requisitos
- Python 3.9+
- Cuenta de WhatsApp Business Cloud API (Meta)
- Railway (servicio web + Postgres)
- Ngrok u otro túnel si pruebas localmente

## Configuración
1) Crear entorno e instalar dependencias:

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows PowerShell
pip install -r requirements.txt
```

2) Variables de entorno:
- Duplica [.env.example](file:///Users/jose/Projects/whatsapp-chatbot/.env.example) a `.env` y ajusta:
  - WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN
  - SECRET_KEY, DEBUG, ALLOWED_HOSTS
  - DATABASE_URL (Railway lo inyecta; localmente puedes usar SQLite)

3) Endpoints:
- GET /meta/verify — verificación de webhook con VERIFY_TOKEN
- POST /meta/webhook — recepción de mensajes y respuesta
- GET /health — estado del servicio

## Ejecutar local

```bash
export DJANGO_SETTINGS_MODULE=clinicbot.settings
python manage.py migrate
python manage.py runserver 0.0.0.0:3000
```

Verificación en Meta (cuando uses túnel):
- Verificación (GET): https://<tu-ngrok>.ngrok.io/meta/verify con tu VERIFY_TOKEN
- Callback (POST): https://<tu-ngrok>.ngrok.io/meta/webhook y suscribe “messages”

## Despliegue en Railway
- Usa [railway.json](file:///Users/jose/Projects/whatsapp-chatbot/railway.json) y [Procfile](file:///Users/jose/Projects/whatsapp-chatbot/Procfile).
- Añade servicio Postgres y variables (WHATSAPP_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN, SECRET_KEY).
- Railway ejecuta migraciones y arranca Gunicorn automáticamente.

## Flujo de conversación
- “menu”/“hola” muestra opciones.
- 1) Nueva cita → nombre, fecha (AAAA-MM-DD) y hora disponible, confirma y guarda.
- 2) Consultar mis citas → lista confirmadas por número.
- 3) Cancelar una cita → solicita el código de confirmación.

Más detalles y ejemplos de código en [INTEGRACION_DJANGO_CLOUD_API.md](file:///Users/jose/Projects/whatsapp-chatbot/INTEGRACION_DJANGO_CLOUD_API.md).
