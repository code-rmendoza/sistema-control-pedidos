from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Crea un backup con datos JSON, media y SQLite si existe."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(settings.BASE_DIR / "backups"),
            help="Carpeta donde se guardara el archivo .zip.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        work_dir = output_dir / f"backup-{timestamp}"
        work_dir.mkdir()
        data_file = work_dir / "data.json"
        zip_file = output_dir / f"backup-{timestamp}.zip"

        call_command(
            "dumpdata",
            exclude=["contenttypes", "auth.permission", "sessions"],
            indent=2,
            output=str(data_file),
        )

        with ZipFile(zip_file, "w", ZIP_DEFLATED) as archive:
            archive.write(data_file, "data.json")

            db_path = settings.BASE_DIR / "db.sqlite3"
            if db_path.exists():
                archive.write(db_path, "db.sqlite3")

            media_root = Path(settings.MEDIA_ROOT)
            if media_root.exists():
                for file_path in media_root.rglob("*"):
                    if file_path.is_file():
                        archive.write(file_path, file_path.relative_to(settings.BASE_DIR))

        data_file.unlink(missing_ok=True)
        work_dir.rmdir()

        self.stdout.write(self.style.SUCCESS(f"Backup creado: {zip_file}"))
