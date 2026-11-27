# Despliegue de Brota en un VPS

Guía para la persona que administra el servidor. Brota es una app móvil (Android) que se
conecta a esta API para respaldar datos, el muro de la comunidad y el «compañero fantasma».

**Qué se despliega:** tres contenedores Docker definidos en `docker-compose.yml`:

| Contenedor | Imagen | Función |
|---|---|---|
| `db` | `postgres:16-alpine` | Base de datos (volumen `datos_postgres`) |
| `api` | se construye con `Dockerfile` (FastAPI + uvicorn, puerto interno 8000) | API REST `/api/v1` |
| `proxy` | se construye con `Dockerfile.caddy` (Caddy 2) | HTTPS con Let's Encrypt automático |

**Recursos:** ~512 MB de RAM y ~1 GB de disco bastan para empezar.

**Repositorio:** <https://github.com/DarvoDev/Backend-Brota> (público, rama `main`).

---

## Lo único que necesitamos de vuelta

Cuando termines, envíanos **el dominio final** (p. ej. `brota.tudominio.com`). Con él
compilamos el APK que se reparte. Debe responder por **HTTPS con un certificado válido**
(Let's Encrypt sirve): Android bloquea HTTP sin cifrar y certificados autofirmados, así que
una IP sola o `BROTA_TLS=internal` no funcionan para los teléfonos.

---

## 1. Antes de empezar

1. **Docker Engine + Compose v2** instalados (`docker compose version`).
2. **Dominio o subdominio** con un registro `A` (y `AAAA` si hay IPv6) apuntando a la IP
   pública del VPS. Comprueba que ya resuelve: `dig +short brota.tudominio.com`.
3. Decide cuál de estos dos casos es el tuyo:
   - **Caso A — los puertos 80 y 443 están libres:** Caddy (incluido) maneja el HTTPS. → Sección 3.
   - **Caso B — ya hay un proxy en 80/443** (nginx, Traefik, Nginx Proxy Manager, Coolify,
     etc.): no se usa Caddy; tu proxy apunta a la API. → Sección 4.

## 2. Variables de entorno

Crea un archivo `.env` junto a `docker-compose.yml` (o ponlas en Portainer →
Stack → *Environment variables*). Todas las secretas son **obligatorias**: si falta una, el
despliegue falla en lugar de arrancar con valores de desarrollo.

```env
# --- Secretos (genera valores propios) ---
POSTGRES_PASSWORD=<aleatorio>
BROTA_JWT_SECRETO=<aleatorio, largo>
BROTA_CLAVE_DATOS=<aleatorio, largo>

# --- Cuenta de administrador de Brota (moderación del muro) ---
ADMIN_CORREO=admin@tudominio.com
ADMIN_PASSWORD=<aleatorio>

# --- HTTPS ---
BROTA_SITIO=brota.tudominio.com
BROTA_TLS=correo-para-letsencrypt@tudominio.com
BROTA_PUERTO_HTTPS=443
BROTA_PUERTO_HTTP=80

# --- Opcionales ---
BROTA_ZONA_HORARIA=America/Mexico_City
BROTA_CORS_ORIGENES=*
```

Para generar cada valor aleatorio:

```bash
openssl rand -base64 48 | tr -d '\n/+=' ; echo
```

> ⚠️ **No cambies `BROTA_CLAVE_DATOS` después del primer despliegue.** Cifra los datos que
> envían los usuarios; si cambia, lo ya guardado no se podrá descifrar. Guárdala junto con
> los demás secretos en un lugar seguro.

> Puertos (opcionales): `API_PUERTO` (8000, solo `127.0.0.1`), `POSTGRES_PUERTO` (5433,
> solo `127.0.0.1`), `API_IP`, `PROXY_IP`. Ver `.env.example`, todas están comentadas.

## 3. Caso A — puertos 80/443 libres (Caddy incluido)

```bash
git clone https://github.com/DarvoDev/Backend-Brota.git
cd Backend-Brota
nano .env        # contenido de la sección 2
docker compose up -d --build
```

- Abre **80/tcp y 443/tcp** en el firewall del VPS y del proveedor (`ufw allow 80,443/tcp`).
  El 80 es necesario para que Let's Encrypt valide el dominio.
- Caddy obtiene y renueva el certificado solo. El primer arranque puede tardar ~1 minuto.
- La API publica el puerto `API_PUERTO` (8000) solo en `127.0.0.1`: desde fuera solo se llega por Caddy.

**Con Portainer:** Stacks → Add stack → Repository → URL del repo, rama `main`,
**Name `brota`**, *Compose path* `docker-compose.yml`, variables de la sección 2 → *Deploy the stack*.

## 4. Caso B — ya existe un proxy en el servidor

No hace falta ningún archivo extra: la API ya se publica en `127.0.0.1:${API_PUERTO}`
(por defecto `127.0.0.1:8000`).

1. En el `.env` / variables de Portainer deja Caddy en puertos libres (no 80/443):
   `BROTA_PUERTO_HTTPS=8443`, `BROTA_PUERTO_HTTP=8080`, `BROTA_TLS=internal`
   (o `PROXY_IP=127.0.0.1` para que ni siquiera se vea desde fuera).
   Si 8000 está ocupado, cambia `API_PUERTO`.

2. Arranca igual que en el caso A: `docker compose up -d --build`.

3. En tu proxy, envía el dominio a `http://127.0.0.1:8000` con su certificado de
   Let's Encrypt. Ejemplo para nginx:

   ```nginx
   server {
       server_name brota.tudominio.com;
       # ... listen 443 ssl + certificados (certbot) ...

       location / {
           proxy_pass         http://127.0.0.1:8000;
           proxy_set_header   Host              $host;
           proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
           proxy_set_header   X-Forwarded-Proto $scheme;
           client_max_body_size 2m;
       }
   }
   ```

   La API ya acepta las cabeceras `X-Forwarded-*` (`--proxy-headers`).
   Si el proxy corre en Docker (Traefik, Nginx Proxy Manager), en lugar de publicar el
   puerto puedes unir el contenedor `api` a la red del proxy y apuntar a `api:8000`.

## 5. Comprobar que funciona

```bash
curl https://brota.tudominio.com/api/v1/salud
# {"estado":"ok","version":"1.0.0"}
```

- Documentación interactiva (Swagger): `https://brota.tudominio.com/docs`
- Estado de los contenedores: `docker compose ps`
  (`api` debe aparecer como `healthy`).
- Logs: `docker compose logs -f api proxy`

Al arrancar por primera vez la API crea las tablas, carga los datos iniciales (catálogo,
mensajes, frases) y la cuenta de administrador de `ADMIN_CORREO` / `ADMIN_PASSWORD`.

## 6. Actualizar

```bash
cd Backend-Brota
git pull
docker compose up -d --build
```

En Portainer: abre el stack → *Pull and redeploy*. Los datos se conservan en los volúmenes.

## 7. Respaldos

```bash
# Respaldo
docker compose exec -T db \
  pg_dump -U brota brota | gzip > brota_$(date +%F).sql.gz

# Restaurar (sobre una base vacía)
gunzip -c brota_AAAA-MM-DD.sql.gz | \
  docker compose exec -T db psql -U brota brota
```

Se recomienda un respaldo diario con `cron`. Guarda también el `.env`: sin
`BROTA_CLAVE_DATOS` el respaldo no sirve.

## 8. Notas de seguridad y privacidad

- La app maneja datos sensibles (estado de ánimo). Se guardan **cifrados** en la base; las
  contraseñas solo como hash (bcrypt). Los contactos de emergencia nunca llegan al servidor.
- No expongas el puerto 5432 de PostgreSQL ni el 8000 de la API a internet.
- **Nunca** borres los volúmenes (`docker compose down -v`) en producción.
- Para detener sin perder datos: `docker compose down`.

## 9. Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `required variable … is missing a value` | Falta una variable de la sección 2 en `.env` |
| Caddy no obtiene certificado | El dominio aún no apunta al VPS, o el puerto 80 está cerrado/ocupado |
| `bind: address already in use` en 80/443 | Ya hay otro proxy → usa el caso B |
| `api` en estado `unhealthy` | Ver `logs api`; normalmente la base aún no estaba lista o un secreto es inválido |
| La app dice «No hay conexión con el servidor» | El dominio no responde por HTTPS válido; prueba el `curl` de la sección 5 desde fuera del VPS |
