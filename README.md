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
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=5432
ALLOWED_HOSTS=tu-dominio.com,127.0.0.1,localhost
```

## Flujo principal

1. Crea clientes.
2. Crea una orden con uno o varios productos.
3. Registra abonos; cada pago crea un ingreso en caja.
4. Actualiza costos reales al comprar.
5. Descarga el PDF del cliente desde el detalle de la orden.
