# Woffy Go - Backend API

Backend de Woffy Go: plataforma para conectar dueños de mascotas con
paseadores caninos en tiempo real (estilo Uber). Incluye motor geoespacial
con PostGIS, autenticacion JWT por roles, ciclo de vida de paseos con
maquina de estados e integracion de pagos con MercadoPago.

## Stack tecnologico

- Python 3.11
- FastAPI 0.115
- PostgreSQL 16 + PostGIS 3.6
- SQLAlchemy 2.0 + Alembic
- Autenticacion: JWT (python-jose) + bcrypt (passlib)
- Pagos: MercadoPago SDK oficial
- Servidor: Uvicorn

## Estructura del proyecto

C:\woffygo
|-- app
| |-- core # Config, database, security, deps
| |-- models # Modelos SQLAlchemy (6 tablas)
| |-- schemas # Schemas Pydantic (validacion)
| |-- routers # Endpoints (auth, walkers, walks, payments)
| |-- services # Logica de negocio (geo, walks, mercadopago)
| |-- seeders # Datos de prueba
| -- main.py # Punto de entrada FastAPI |-- alembic # Migraciones |-- venv # Entorno virtual |-- .env # Variables de entorno (NO subir a git)-- requirements.txt # Dependencias

## Como levantar el backend

1. Activar el entorno virtual:

2. Levantar el servidor:

3. Abrir la documentacion interactiva en el navegador:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Como resetear la base con datos de prueba


Crea:
- 1 admin (admin@woffygo.com)
- 2 duenios (juan@example.com, maria@example.com)
- 2 paseadores (carlos@example.com, lucia@example.com)
- 3 mascotas (Toby, Luna, Rocky)

Password para todos: `test123`

## Endpoints principales

### Autenticacion
- `POST /auth/register` - Crear usuario
- `POST /auth/login` - Login (devuelve JWT)
- `GET /auth/me` - Datos del usuario autenticado
- `PATCH /auth/me` - Actualizar perfil

### Paseadores
- `POST /walkers/profile` - Crear perfil (solo WALKER)
- `GET /walkers/profile/me` - Ver mi perfil
- `PATCH /walkers/profile/me` - Editar mi perfil
- `POST /walkers/location` - Actualizar ubicacion GPS
- `POST /walkers/online` - Cambiar online/offline
- `GET /walkers/nearby?latitude=..&longitude=..&radius_km=..` - Buscar cercanos

### Paseos (maquina de estados)
- `POST /walks` - Crear paseo (solo OWNER)
- `GET /walks` - Listar mis paseos
- `GET /walks/available` - Pendientes sin asignar (solo WALKER)
- `GET /walks/{id}` - Detalle
- `POST /walks/{id}/accept` - Aceptar (WALKER, calcula precio)
- `POST /walks/{id}/start` - Iniciar (WALKER asignado)
- `POST /walks/{id}/finish` - Finalizar (incrementa total_walks)
- `POST /walks/{id}/cancel` - Cancelar

### Pagos
- `POST /payments/checkout/{walk_id}` - Generar link de pago (solo OWNER)
- `GET /payments/{walk_id}` - Estado del pago
- `POST /payments/webhook` - Webhook publico de MercadoPago
- `GET /payments/return/{success|failure|pending}` - Retornos del checkout

## Flujo completo de un paseo

1. OWNER crea un paseo -> estado `pendiente`
2. WALKER lo ve en `/walks/available` y lo acepta -> estado `aceptado` + precio calculado
3. OWNER genera checkout con `/payments/checkout/{id}` -> obtiene `init_point`
4. OWNER paga en MercadoPago -> webhook actualiza `Payment` a `aprobado`
5. WALKER inicia el paseo -> estado `en_proceso`
6. WALKER lo finaliza -> estado `completado` + `total_walks` incrementado

## Comision de plataforma

- **15%** sobre el precio total del paseo.
- Ejemplo: paseo de 1 hora a $2500/h = $2500 total
  - Comision Woffy Go: **$375**
  - Ganancia del paseador: **$2125**

## Variables de entorno (.env)

DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/woffygo_db
SECRET_KEY=<clave secreta JWT>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
MERCADOPAGO_ACCESS_TOKEN=<token de prueba o produccion>
MERCADOPAGO_PUBLIC_KEY=<public key>
MERCADOPAGO_WEBHOOK_SECRET=<secreto del webhook>

## Estado actual

- [x] FASE 1 - Paso 1: Infraestructura y modelos
- [x] FASE 1 - Paso 2: Autenticacion JWT y roles
- [x] FASE 1 - Paso 3: Motor geoespacial (PostGIS)
- [x] FASE 1 - Paso 4: Ciclo de vida de paseos
- [x] FASE 1 - Paso 5: Integracion MercadoPago
- [ ] FASE 1 - Paso 6: Pruebas integrales y documentacion
- [ ] FASE 2: Aplicacion movil