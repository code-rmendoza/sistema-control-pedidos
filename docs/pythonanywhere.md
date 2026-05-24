# Despliegue Gratis En PythonAnywhere

Esta guia es para la opcion inicial sin pago: PythonAnywhere Free con SQLite y archivos `media/` dentro del proyecto.

## 1. Crear Cuenta Y Consola

1. Crea una cuenta free en PythonAnywhere.
2. Abre una consola Bash.
3. Clona el repositorio:

```bash
git clone https://github.com/code-rmendoza/sistema-control-pedidos.git sistemaImport
cd sistemaImport
```

## 2. Crear Virtualenv

Usa Python 3.12 o superior, porque Django 6 lo requiere.

```bash
mkvirtualenv --python=/usr/bin/python3.12 sistemaImport
pip install -r requirements.txt
```

## 3. Restaurar Data Real

En tu PC local crea un backup:

```powershell
.\.venv\Scripts\python manage.py backup_data
```

Sube el `.zip` generado a PythonAnywhere. Luego en Bash:

```bash
unzip backup-YYYYMMDD-HHMMSS.zip -d backup-restaurado
cp backup-restaurado/db.sqlite3 ~/sistemaImport/db.sqlite3
cp -R backup-restaurado/media ~/sistemaImport/
```

Si prefieres restaurar desde JSON:

```bash
python manage.py migrate
python manage.py loaddata backup-restaurado/data.json
cp -R backup-restaurado/media ~/sistemaImport/
```

## 4. Variables De Produccion

En PythonAnywhere Free, la forma simple es colocarlas en el archivo WSGI.

1. Abre `deploy/pythonanywhere_wsgi.py`.
2. Confirma que `USERNAME = "rmendoza"`.
3. Genera una clave secreta nueva y reemplaza el valor de `SECRET_KEY` en el WSGI:

```python
os.environ["SECRET_KEY"] = "pega-aqui-una-clave-larga-y-secreta"
```

Puedes generar una clave desde consola:

```bash
python - <<'PY'
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
PY
```

## 5. Static Y Migraciones

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
```

## 6. Crear Web App

En la pestana **Web** de PythonAnywhere:

1. Crea una nueva web app.
2. Elige **Manual configuration**.
3. Selecciona Python 3.12 o superior.
4. En **Virtualenv**, coloca:

```text
/home/rmendoza/.virtualenvs/sistemaImport
```

5. En el archivo WSGI de PythonAnywhere, copia el contenido de:

```text
deploy/pythonanywhere_wsgi.py
```

Recuerda cambiar el usuario y `SECRET_KEY`.

## 7. Static Files En La Pestana Web

Agrega estos mappings:

```text
URL: /static/
Directory: /home/rmendoza/sistemaImport/staticfiles
```

```text
URL: /media/
Directory: /home/rmendoza/sistemaImport/media
```

Luego presiona **Reload**.

## 8. Advertencias Importantes

- PythonAnywhere Free tiene almacenamiento limitado. Vigila el peso de `media/`.
- El boton **Traer imagen** puede fallar por restricciones de internet saliente del plan free.
- Haz backups frecuentes desde local y desde PythonAnywhere.
- Cuando el negocio crezca, conviene migrar a PostgreSQL y almacenamiento de imagenes persistente.
