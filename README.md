# Brota — Backend

API REST de **Brota**, la app gamificada de hábitos para jóvenes que procrastinan o
pasan por días de ánimo bajo (proyecto escolar, Equipo 1).

La app Flutter funciona **100 % sin conexión**; este backend es opcional y, cuando se
configura, aporta:

- cuentas con JWT (registro con reglas de edad y consentimiento),
- sincronización **sin duplicados** de los datos de la app (RNF-07), cifrados en reposo (RNF-02),
- un **compañero fantasma** anónimo real (señales y reacciones entre usuarios),
- un **muro de aliento** moderado (solo frases predefinidas o logros, autoocultado con reportes),
- contenido administrable (catálogo de micro-misiones, mensajes validados, directorio de ayuda),
- el **clasificador por diccionario** de mensajes y el **perceptrón** de riesgo de procrastinación.

El contrato completo de la API está en [`docs/CONTRATO_API.md`](docs/CONTRATO_API.md).

## Arquitectura (3 capas)

```
┌──────────────────────┐   HTTPS / JSON    ┌──────────────────────────┐   SQL   ┌──────────────┐
│  Cliente Flutter     │ ────────────────▶ │  API REST (FastAPI)      │ ──────▶ │ PostgreSQL 16│
│  (brota_app, offline │   Caddy :8443     │  uvicorn :8000           │         │  (volumen)   │
│   first, SQLite)     │ ◀──────────────── │  JWT · bcrypt · Fernet   │ ◀────── │              │
└──────────────────────┘                   └──────────────────────────┘         └──────────────┘
```

| Servicio (docker compose) | Imagen | Puerto | Función |
|---|---|---|---|
| `db` | `postgres:16-alpine` | interno 5432 | Base de datos con volumen y healthcheck |
| `api` | `Dockerfile` (python:3.12-slim, usuario sin privilegios) | **8000** (HTTP) | La API |
| `proxy` | `Dockerfile.caddy` (caddy:2-alpine + Caddyfile) | **8443** (HTTPS) | Termina TLS (`tls internal` o Let's Encrypt) y reenvía a `api` |

Estructura del código:

```
app/
  main.py            # crea la app, CORS, errores en español, arranque (tablas + semilla)
  config.py          # variables de entorno y utilidades de fecha
  db.py, modelos.py  # SQLAlchemy 2 (create_all, sin migraciones)
  esquemas.py        # validación de entradas (pydantic v2)
  seguridad.py       # bcrypt, JWT HS256, cifrado Fernet, dependencias de rol
  clasificador.py    # clasificador por diccionario de palabras clave
  perceptron.py      # perceptrón en Python puro
  semilla.py         # carga semilla.json y crea el administrador
  rutas/             # un archivo por módulo de la API
  datos/             # diccionario_motivacional.json y semilla.json
tests/               # pytest con SQLite en memoria
```

## Cómo ejecutarlo

Requisitos: Docker Desktop (o Docker Engine con Compose v2).

```bash
cp .env.example .env      # obligatorio: el compose exige los secretos (los de ejemplo sirven en local)
docker compose up --build
```

- API en HTTP: <http://localhost:8000/api/v1/salud>
- API en HTTPS: <https://localhost:8443/api/v1/salud> (certificado autofirmado: `curl -k`)
- Documentación interactiva (Swagger): <http://localhost:8000/docs>

Al arrancar se crean las tablas, se carga `semilla.json` si las tablas están vacías y se
crea la cuenta de administrador definida en `ADMIN_CORREO` / `ADMIN_PASSWORD`.

Para detenerlo: `docker compose down` (agrega `-v` para borrar también los datos).

### En un servidor con Portainer

Local y servidor usan el mismo `docker-compose.yml` (stack `brota`). No monta archivos del
host (el `Caddyfile` va dentro de la imagen `Dockerfile.caddy`) y **exige** los secretos: si
falta alguno, el despliegue falla en lugar de arrancar con valores inseguros. Los puertos
publicados también salen de variables.

1. Portainer → **Stacks** → **Add stack** → **Name: `brota`** → **Repository**.
2. URL de este repositorio (y credenciales si es privado), rama `main`,
   **Compose path**: `docker-compose.yml`.
3. En **Environment variables** → *Load variables from .env file*: pega `.env.example` con
   tus valores (todas están comentadas ahí):

   | Variable | Ejemplo | Obligatoria |
   |---|---|---|
   | `POSTGRES_PASSWORD` | cadena aleatoria | sí |
   | `BROTA_JWT_SECRETO` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | sí |
   | `BROTA_CLAVE_DATOS` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | sí |
   | `ADMIN_CORREO` / `ADMIN_PASSWORD` | cuenta del administrador | sí |
   | `BROTA_SITIO` | `192.168.1.50` o `brota.midominio.com` (defecto: localhost) | no |
   | `BROTA_TLS` | `internal` (defecto) o un correo para Let's Encrypt | no |
   | `BROTA_SNI_DEFECTO` | por defecto igual a `BROTA_SITIO`; defínela si `BROTA_SITIO` lleva varias direcciones | no |
   | `API_IP` / `API_PUERTO` | `127.0.0.1` / `8000` (defecto): API en HTTP plano | no |
   | `PROXY_IP` / `BROTA_PUERTO_HTTPS` / `BROTA_PUERTO_HTTP` | `0.0.0.0` / `8443` / `8080` (defecto); con Let's Encrypt `443` / `80` | no |
   | `POSTGRES_PUERTO` | `5433` (defecto), solo en `127.0.0.1` del host | no |
   | `BROTA_CORS_ORIGENES`, `BROTA_ZONA_HORARIA` | igual que en desarrollo | no |

   Si el servidor ya tiene otro proxy en 80/443, deja Caddy en puertos libres y apunta tu
   proxy a `http://127.0.0.1:<API_PUERTO>`.

4. **Deploy the stack**. Portainer clona el repo y construye las imágenes `brota-api` y
   `brota-proxy`. Para actualizar tras un `git push`: abre el stack → **Pull and redeploy**
   (marca *Re-pull image and redeploy*), o activa **GitOps updates**.

Dos modos de HTTPS:

- **Solo IP** (red local / escuela): `BROTA_SITIO=<IP del servidor>`, `BROTA_TLS=internal`.
  La app usa `https://<IP>:8443/api/v1` y debe confiar en la CA interna de Caddy; cópiala con
  `docker cp <contenedor-proxy>:/data/caddy/pki/authorities/local/root.crt .`
  (Portainer → Containers → proxy → Console también sirve).
- **Dominio propio**: el dominio debe apuntar a la IP pública del servidor;
  `BROTA_SITIO=brota.midominio.com`, `BROTA_TLS=tu@correo.com`,
  `BROTA_PUERTO_HTTPS=443`, `BROTA_PUERTO_HTTP=80` (ambos abiertos en el firewall).
  Caddy obtiene y renueva el certificado de Let's Encrypt solo. URL: `https://brota.midominio.com/api/v1`.

Los datos viven en los volúmenes `datos_postgres` y `datos_caddy`; borrar el stack no los
borra salvo que también elimines los volúmenes. **No cambies `BROTA_CLAVE_DATOS`** después
del primer despliegue: los datos sincronizados ya guardados dejarían de poder descifrarse.

### Sin Docker (desarrollo rápido)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # usa SQLite local (brota_local.db) si no hay DATABASE_URL
```

## Variables de entorno

| Variable | Para qué sirve | Valor por defecto (solo desarrollo) |
|---|---|---|
| `DATABASE_URL` | Conexión SQLAlchemy | En Docker: `postgresql+psycopg://brota:…@db:5432/brota`; fuera: `sqlite:///./brota_local.db` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL (docker compose) | `brota-dev` |
| `BROTA_JWT_SECRETO` | Secreto para firmar los JWT (HS256) | `secreto-de-desarrollo-cambialo` |
| `BROTA_CLAVE_DATOS` | Clave Fernet para cifrar los datos sincronizados. Si no es una clave Fernet válida se deriva una con SHA-256 | `clave-de-datos-de-desarrollo-cambiala` |
| `ADMIN_CORREO` / `ADMIN_PASSWORD` | Administrador que se crea al arrancar | `admin@brota.local` / `admin-brota-dev` |
| `BROTA_CORS_ORIGENES` | Orígenes CORS separados por coma | `*` |
| `BROTA_ZONA_HORARIA` | Zona para decidir "qué día es hoy" | `America/Mexico_City` |

La API muestra una advertencia en el log mientras se usen los secretos de desarrollo.
**Nunca subas el archivo `.env` al repositorio** (ya está en `.gitignore`).

## Cómo se conecta la app

En la pantalla de ajustes de la app se escribe la **URL del servidor** (base, incluye `/api/v1`):

| Dónde corre la app | URL |
|---|---|
| Emulador de Android | `http://10.0.2.2:8000/api/v1` (o `https://10.0.2.2:8443/api/v1`) |
| Celular físico en la misma red Wi-Fi | `http://<IP-de-tu-PC>:8000/api/v1` |
| Escritorio / navegador en la misma PC | `http://localhost:8000/api/v1` |

El certificado HTTPS de Caddy es autofirmado (CA interna). Para usar el puerto 8443 desde
la app en desarrollo hay que confiar en ese certificado o aceptarlo explícitamente. La CA
raíz se puede copiar con
`docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt .`.
Para usar HTTPS desde otra IP agrégala con la variable `BROTA_SITIO` (p. ej.
`BROTA_SITIO=localhost, 10.0.2.2, 192.168.1.50`).

## Endpoints

Base `/api/v1`. Errores siempre como `{"detail": "<mensaje en español>"}`.
🔒 = requiere `Authorization: Bearer <jwt>`; 👑 = solo rol `administrador` (si no, 403).

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/salud` | Estado del servicio |
| POST | `/auth/registro` | Crear cuenta (edad ≥ 13; 13–17 con consentimiento de tutor; > 35 con aviso) |
| POST | `/auth/login` | Iniciar sesión |
| GET | `/auth/yo` 🔒 | Datos de mi cuenta |
| POST | `/sync` 🔒 | Subir lote de eventos (idempotente) → `aceptados` / `duplicados` / `rechazados` |
| GET | `/sync/resumen` 🔒 | Conteo de eventos por tipo y última sincronización |
| POST | `/fantasma/senales` 🔒 | "Completé mi misión de hoy" (1 por día) |
| GET | `/fantasma/senales` 🔒 | Hasta 10 señales anónimas de otros (últimas 24 h) |
| POST | `/fantasma/reacciones` 🔒 | Reaccionar a una señal (`bien_hecho`, `tu_puedes`, `sigue_asi`) |
| GET | `/fantasma/recibidas` 🔒 | Reacciones recibidas aún no entregadas |
| GET | `/comunidad/frases` | Frases predefinidas del muro |
| GET | `/comunidad/publicaciones` 🔒 | Publicaciones visibles (máx. 50) |
| POST | `/comunidad/publicaciones` 🔒 | Publicar `{"frase_id"}` o `{"logro":{"racha","xp"}}` (sin texto libre) |
| POST | `/comunidad/publicaciones/{id}/reportes` 🔒 | Reportar; con 3 reportes se oculta sola |
| GET | `/admin/reportes` 👑 | Reportes pendientes |
| POST | `/admin/reportes/{id}/resolver` 👑 | `{"accion":"ocultar"\|"mantener"}` |
| POST | `/mensajes/clasificar` | Clasificar un texto con el diccionario |
| GET | `/mensajes/diccionario` | El diccionario completo (JSON) |
| GET | `/contenido/catalogo` · `/contenido/mensajes` · `/contenido/directorio` | Contenido público |
| POST · PUT · DELETE | `/admin/catalogo[/{id}]` 👑 | Administrar micro-misiones |
| POST · PUT · DELETE | `/admin/mensajes[/{id}]` 👑 | Administrar mensajes (solo se aceptan si se clasifican como `motivadora`) |
| POST · PUT · DELETE | `/admin/directorio[/{id}]` 👑 | Administrar el directorio de ayuda |
| POST | `/riesgo/prediccion` 🔒 | Predicción del perceptrón (`{"x":[8]}` o `{}` para calcularla con lo sincronizado) |
| POST | `/riesgo/entrenar` 🔒 | Reentrenar los pesos del usuario con su historial |

Los identificadores que genera el servidor (usuarios, señales, reacciones, publicaciones,
reportes) son cadenas UUID.

## Seguridad

- **Contraseñas** con **bcrypt** (sal por contraseña); nunca se guardan en texto plano.
- **JWT HS256** con expiración de 7 días; `sub` = id de usuario y `rol`. El rol se vuelve a
  comprobar en la base de datos en cada petición de administración.
- **Cifrado en reposo (RNF-02)**: el campo `datos` de cada evento sincronizado (ánimo,
  energía, cumplimientos…) se guarda cifrado con **Fernet** (AES-128-CBC + HMAC-SHA256)
  usando `BROTA_CLAVE_DATOS`. En la tabla `eventos_sync` solo se ve el texto cifrado.
- **HTTPS** mediante **Caddy** (`tls internal`) en el puerto 8443. El puerto 8000 en HTTP
  queda solo para desarrollo local y el emulador.
- **Privacidad del fantasma**: las señales y reacciones solo exponen ids opacos y minutos
  transcurridos; nunca nombres ni correos.
- **Muro sin texto libre**: solo frases predefinidas o logros numéricos; 3 reportes de
  usuarios distintos la ocultan hasta que un administrador decida.
- La imagen de la API corre con un usuario **sin privilegios**.

## Clasificador por diccionario

`app/datos/diccionario_motivacional.json` agrupa términos en categorías con un peso
(p. ej. `proceso_logro` +2, `presion_culpa` −2). El algoritmo (idéntico en la app):

1. Normalizar: minúsculas, quitar acentos (NFD), todo lo que no sea `a-z`/`0-9` → espacio.
2. Recorrer los términos de más a menos palabras (empates: orden del archivo).
3. Cada término se busca una sola vez; sus palabras no pueden estar ya usadas por otro
   término (así "no tienes que" no cuenta también como "tienes que"). `*` = prefijo.
4. Reglas: término de `riesgo` → `riesgo`; término `ofensiva` → `no_apta`; si no, puntaje
   = suma de pesos: ≥ 2 → `motivadora`, ≤ −1 → `no_apta`, otro → `neutra`. Estilo
   `explicito` si hay una exhortación explícita ("tú puedes"), si no `implicito`.

Un administrador solo puede publicar mensajes que salgan como `motivadora`.

## Perceptrón de riesgo de procrastinación

Un perceptrón de 8 entradas (todas en 0..1) calculadas al cierre del día *d* para predecir
el día *d+1*: constancia de 7 días, hora media de los cumplimientos, escudos de la semana,
si mañana es fin de semana, actividad con el fantasma, último ánimo, última energía y si
hubo cumplimiento hoy.

- Pesos iniciales `w = [-1.2, 0.4, 0.6, 0.3, -0.4, -0.8, -0.6, -1.0]`, `b = 1.4`.
- `z = w·x + b`; **ALTO** si `z > 0`, si no **BAJO**.
- Aprendizaje (η = 0.1): `y = 1` si no hubo cumplimiento en *d+1*;
  `wᵢ ← wᵢ + η(y−ŷ)xᵢ`, `b ← b + η(y−ŷ)`.
- `/riesgo/entrenar` parte de los pesos iniciales y recorre el historial sincronizado del
  usuario día por día (del primer al penúltimo día con datos), guardando los pesos
  resultantes en la tabla `pesos_riesgo`.

Está escrito en Python puro (`app/perceptron.py`). **El modelo no diagnostica nada**: solo
sirve para que la app ajuste la dificultad de las misiones del día siguiente.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```

Las pruebas usan SQLite en memoria (dependency override de la sesión) y cubren: registro y
reglas de edad/consentimiento, login, sincronización idempotente, cifrado en reposo,
reglas del fantasma, muro (solo frases predefinidas, autoocultado con 3 reportes,
resolución del admin), los ejemplos del diccionario, validación de mensajes del admin,
el perceptrón (predicción y un paso de aprendizaje) y los permisos por rol (403).
