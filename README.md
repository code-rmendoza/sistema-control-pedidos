# Plataforma Web Para Gestion De Importaciones

App privada en Django para registrar clientes, ordenes, productos importados, pagos parciales, caja simple y reportes PDF para enviar al cliente.

## Ejecutar en desarrollo

```powershell
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py createsuperuser
.\.venv\Scripts\python manage.py runserver
```

Luego abre `http://127.0.0.1:8000/`.

## Base de datos

En desarrollo usa SQLite por defecto. Para desplegar con PostgreSQL, define estas variables:

```text
DJANGO_ENV=production
DEBUG=false
SECRET_KEY=una-clave-larga-y-secreta
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=5432
ALLOWED_HOSTS=tu-dominio.com,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
```

Para ver todas las variables esperadas, usa `.env.example`.

## Preparar produccion

```powershell
pnpm.cmd build
.\.venv\Scripts\python manage.py collectstatic --noinput
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py check --deploy
```

En produccion usa `DJANGO_ENV=production`, `DEBUG=false`, una `SECRET_KEY` nueva y el dominio real en `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.

Para el despliegue gratis inicial en PythonAnywhere, sigue [docs/pythonanywhere.md](docs/pythonanywhere.md).

## Backups

Antes de subir a produccion o antes de cambios grandes:

```powershell
.\.venv\Scripts\python manage.py backup_data
```

Esto crea un `.zip` en `backups/` con:

- `data.json`: datos exportados con Django.
- `media/`: imagenes subidas al sistema.
- `db.sqlite3`: copia de la base local si existe.

Para restaurar datos en una instalacion limpia:

```powershell
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py loaddata ruta\al\data.json
```

Tambien debes restaurar la carpeta `media/` del backup para que las imagenes subidas sigan visibles.

## Flujo principal

1. Crea clientes.
2. Crea una orden con uno o varios productos.
3. Registra abonos; cada pago crea un ingreso en caja.
4. Actualiza costos reales al comprar.
5. Descarga el PDF del cliente desde el detalle de la orden.
