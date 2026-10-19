\# 🗺️ ROADMAP OFICIAL \& ESTADO DEL PROYECTO — WOFFY GO



\*\*Fecha de última actualización:\*\* Octubre 2026

\*\*Entorno de Producción Backend:\*\* Render (https://woffygo-api.onrender.com)

\*\*Base de Datos:\*\* PostgreSQL 16 + PostGIS 3.6

\*\*App Móvil:\*\* React Native / Expo (Mapbox, Geocoding, Tracking Background)

\*\*Contexto Operativo:\*\* Villa Carlos Paz, Córdoba, Argentina



\---



\## 📊 RESUMEN EJECUTIVO DE PROGRESO



\[FASE 1: Fundaciones, Modelos \& Auth]     ████████████████████ 100% (COMPLETADO)

\[FASE 2: Core Paseos (WALK)]              ████████████████████ 100% (COMPLETADO)

\[FASE 3: Pet Taxi / Traslados (TRANSPORT)]████████████████████ 100% (COMPLETADO)

\[FASE 4: Estabilización, E2E \& Deploy]    ████████████████████ 100% (COMPLETADO)

\[FASE 5: Pasarela Mercado Pago (Real)]    █████████████░░░░░░░  65% (EN CURSO)

\[FASE 6: Verificación KYC \& Cloudinary]   ████████████░░░░░░░░  60% (EN CURSO)

\[FASE 7: Módulo Guardería (DAYCARE)]      ████░░░░░░░░░░░░░░░░  20% (PLANIFICADO)

\[FASE 8: Pruebas de Campo \& Lanzamiento]  ██░░░░░░░░░░░░░░░░░░  10% (PENDIENTE)





\---



\## 🟢 1. FUNCIONALIDADES COMPLETADAS (100% OPERATIVAS)



\### 1.1 Arquitectura e Infraestructura

\- \*\*Backend API:\*\* FastAPI 0.115 desplegado y en vivo en Render (Live vía Gunicorn + Uvicorn).

\- \*\*Motor Geoespacial:\*\* PostgreSQL con PostGIS 3.6 mapeando geometrías con geoalchemy2 (WKTElement SRID 4326) para orígenes, destinos y rutas.

\- \*\*Autenticación y Seguridad:\*\* JWT con caducidad, hashing de contraseñas con bcrypt (passlib), control de acceso por roles (OWNER, WALKER, ADMIN).

\- \*\*Limpieza de Repositorios:\*\* Eliminación total de archivos temporales .bak, configuración de .gitignore para binarios .apk, ramas main sincronizadas en GitHub.



\### 1.2 Core de Servicios: Paseos (WALK)

\- \*\*Máquina de Estados Robusta:\*\* REQUESTED -> ACCEPTED -> IN\_PROGRESS -> COMPLETED / CANCELLED.

\- \*\*Telemetría GPS en Vivo:\*\* Registro de coordenadas en walk\_locations y dibujado de polylines en tiempo real mediante Mapbox.

\- \*\*Gestión de Mascotas:\*\* Asignación de una o varias mascotas a un paseo con ficha médica y notas.

\- \*\*Chat Interno:\*\* Mensajería en tiempo real entre dueño y paseador activa durante el servicio.

\- \*\*Reseñas \& Reputación:\*\* Sistema de calificación 1 a 5 estrellas y comentarios (Review).



\### 1.3 Módulo Pet Taxi / Traslados (TRANSPORT)

\- \*\*Cotización y Creación:\*\* Pantalla dedicada CreateTransportScreen con cálculo dinámico de tarifas, comisiones de plataforma (platform\_fee) y ganancia neta (provider\_earnings).

\- \*\*Geocodificación:\*\* Soporte de direcciones de origen y notas de destino.

\- \*\*Prueba End-to-End Validada:\*\* Flujo integral de 7 etapas testeado con éxito contra la base de datos (creación, asignación, inicio, grabación de puntos GPS, finalización, liquidación de pago y reseña).



\### 1.4 Interfaz de Usuario y Estabilidad Móvil

\- \*\*Normalización de Estados:\*\* Capa de abstracción statusNormalizer.ts para resolver discrepancias entre enums de base de datos e interfaz en español.

\- \*\*Correcciones en WalkDetailScreen:\*\*

&#x20; - Resuelto el ReferenceError: Property 'serviceLabel' doesn't exist.

&#x20; - El botón 'Cancelar' se oculta de forma estricta cuando el servicio está finalizado (COMPLETED).



\---



\## 🟡 2. EN CURSO (REQUISITOS PREVIOS AL LANZAMIENTO COMERCIAL)



\### 2.1 Fase 5: Conexión Real con Mercado Pago (65%)

\- \*\*Lo que está hecho:\*\* 

&#x20; - Modelo Payment con estados contables (pendiente, aprobado, liberado, reembolsado).

&#x20; - Lógica de retención (escrow) y liberación automática al finalizar el servicio.

\- \*\*Lo que falta:\*\*

&#x20; - Generación de Checkout Pro Preference ID real mediante SDK oficial de Mercado Pago.

&#x20; - Endpoint de Webhook / IPN (/payments/webhook) para confirmación asíncrona de cobro con tarjeta o saldo en cuenta.



\### 2.2 Fase 6: Verificación de Identidad (KYC) \& Cloudinary (60%)

\- \*\*Lo que está hecho:\*\*

&#x20; - Panel administrativo (AdminUsersScreen, AdminStatsScreen) con métricas y visualización de prestadores.

&#x20; - Servicio base de integración con Cloudinary.

\- \*\*Lo que falta:\*\*

&#x20; - Flujo móvil de onboarding del prestador para captura y subida de DNI y antecedentes a Cloudinary.

&#x20; - Bloqueo preventivo: un paseador/chofer no puede aceptar servicios hasta que el admin apruebe sus documentos.



\---



\## ⚪ 3. PENDIENTE / ROADMAP POST-MVP



\### 3.1 Fase 7: Módulo Guardería / Hotel Canino (DAYCARE) (20%)

\- \*\*Estado actual:\*\* Definido el enum ServiceType.DAYCARE y soporte estructural en tabla bookings.

\- \*\*Por desarrollar:\*\*

&#x20; - Pantalla para selección de rango de fechas (check-in / check-out por noches o días completos).

&#x20; - Flujo de diario fotográfico (bitácora diaria con fotos subidas por el cuidador para tranquilidad del dueño).



\### 3.2 Fase 8: Pruebas de Campo \& Lanzamiento en Tiendas (10%)

\- \*\*Pruebas de Campo:\*\* Salida a la calle con dos dispositivos físicos (Dueño y Paseador/Chofer) para comprobar:

&#x20; - Consumo de batería y precisión del GPS en segundo plano con pantalla bloqueada.

&#x20; - Llegada de notificaciones push de asignación y cambio de estado.

\- \*\*Publicación:\*\*

&#x20; - Configuración de perfiles de producción en EAS (eas build --profile production).

&#x20; - Generación de keystore de firma para Google Play Console y certificados para Apple App Store.



\---



\## 🛠️ REGLAS DE ORO DEL PROYECTO

1\. \*\*Estabilidad Primero:\*\* Nunca romper la compatibilidad de base de datos entre Walk y Booking.

2\. \*\*Coordenadas PostGIS:\*\* Toda inserción geográfica debe usar WKTElement('POINT(lon lat)', srid=4326).

3\. \*\*Limpieza Git:\*\* Prohibido commitear archivos .bak, binarios pesados (.apk) o credenciales en texto

