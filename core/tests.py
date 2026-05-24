from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client as HttpClient
from django.test import TestCase
from django.urls import reverse

from .models import Cliente, Envio, ItemPedido, MovimientoCaja, Orden, OrdenEnvio, Pago
from .views import sincronizar_envio_caja


class ImportacionesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="clave-segura")
        self.http = HttpClient()
        self.http.force_login(self.user)
        self.cliente = Cliente.objects.create(nombre="Mayelin Vane", telefono="0412")
        self.orden = Orden.objects.create(cliente=self.cliente, inicial_sugerida=Decimal("10.00"))
        ItemPedido.objects.create(
            orden=self.orden,
            descripcion="Organizador",
            sku="sh123",
            precio_final=Decimal("20.00"),
            costo_estimado=Decimal("12.00"),
        )
        ItemPedido.objects.create(
            orden=self.orden,
            descripcion="Lampara",
            sku="sh456",
            precio_final=Decimal("10.00"),
            costo_estimado=Decimal("5.00"),
            costo_real=Decimal("4.00"),
        )

    def test_order_totals_and_profit(self):
        self.assertEqual(self.orden.total_final, Decimal("30.00"))
        self.assertEqual(self.orden.total_pagado, Decimal("0.00"))
        self.assertEqual(self.orden.saldo_pendiente, Decimal("30.00"))
        self.assertEqual(self.orden.ganancia_estimada, Decimal("13.00"))
        self.assertEqual(self.orden.ganancia_real, Decimal("14.00"))

    def test_order_form_uses_real_cost_label_hooks(self):
        response = self.http.get(reverse("orden_editar", args=[self.orden.pk]))
        content = response.content.decode("utf-8")
        self.assertIn("Costo usado", content)
        self.assertIn("data-item-profit-label", content)
        self.assertIn("Ganancia</dt>", content)

    def test_backup_command_creates_zip_with_data_json(self):
        with TemporaryDirectory() as tmp_dir:
            call_command("backup_data", output_dir=tmp_dir)
            backups = list(Path(tmp_dir).glob("backup-*.zip"))
            self.assertEqual(len(backups), 1)
            with ZipFile(backups[0]) as archive:
                self.assertIn("data.json", archive.namelist())

    def test_create_order_keeps_historical_date(self):
        response = self.http.post(reverse("orden_crear"), {
            "cliente": self.cliente.pk,
            "fecha": "2026-02-14",
            "estado": Orden.Estado.COTIZADA,
            "inicial_sugerida": "0.00",
            "notas": "Carga historica",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-imagen_url": "",
            "items-0-link": "",
            "items-0-tienda": ItemPedido.Tienda.SHEIN,
            "items-0-sku": "hist-1",
            "items-0-descripcion": "Producto historico",
            "items-0-precio_final": "25.00",
            "items-0-costo_estimado": "10.00",
            "items-0-costo_real": "",
            "items-0-precio_shein_eeuu": "",
            "items-0-precio_shein_espana": "",
            "items-0-precio_shein_venezuela": "",
            "items-0-precio_shein_colombia": "",
            "items-0-proveedor_version": ItemPedido.VersionProveedor.EEUU,
        })
        orden = Orden.objects.exclude(pk=self.orden.pk).get()
        self.assertRedirects(response, orden.get_absolute_url())
        self.assertEqual(orden.fecha.isoformat(), "2026-02-14")
        self.assertEqual(orden.total_final, Decimal("25.00"))

    def test_dashboard_month_filter_uses_order_payment_and_freight_dates(self):
        self.orden.fecha = date(2026, 2, 14)
        self.orden.save(update_fields=["fecha"])
        Pago.objects.create(orden=self.orden, fecha=date(2026, 2, 15), monto=Decimal("12.00"))
        MovimientoCaja.objects.create(
            fecha=date(2026, 1, 31),
            tipo=MovimientoCaja.Tipo.INGRESO,
            categoria=MovimientoCaja.Categoria.OTRO,
            descripcion="Saldo anterior",
            monto=Decimal("20.00"),
        )
        MovimientoCaja.objects.create(
            fecha=date(2026, 2, 15),
            tipo=MovimientoCaja.Tipo.INGRESO,
            categoria=MovimientoCaja.Categoria.COBRO_CLIENTE,
            descripcion="Cobro febrero",
            monto=Decimal("12.00"),
        )
        MovimientoCaja.objects.create(
            fecha=date(2026, 5, 15),
            tipo=MovimientoCaja.Tipo.INGRESO,
            categoria=MovimientoCaja.Categoria.COBRO_CLIENTE,
            descripcion="Cobro actual",
            monto=Decimal("99.00"),
        )
        envio = Envio.objects.create(
            nombre="Febrero",
            estado=Envio.Estado.EN_TRANSITO,
            fecha_salida=date(2026, 2, 20),
            fecha_pago_flete=date(2026, 2, 20),
            periodo_utilidad=date(2026, 2, 1),
            costo_flete=Decimal("4.00"),
        )
        OrdenEnvio.objects.create(envio=envio, orden=self.orden, costo_flete_asignado=Decimal("4.00"))
        MovimientoCaja.objects.create(
            fecha=date(2026, 2, 20),
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.FLETE,
            descripcion="Flete febrero",
            monto=Decimal("4.00"),
        )

        response = self.http.get(reverse("dashboard"), {"mes": "2026-02"})
        payload = response.context["dashboard_payload"]
        self.assertEqual(payload["mes"], "2026-02")
        self.assertEqual(payload["vendidoMes"], "30.00")
        self.assertEqual(payload["cobradoMes"], "12.00")
        self.assertEqual(payload["saldoInicialCaja"], "20.00")
        self.assertEqual(payload["movimientoCaja"], "8.00")
        self.assertEqual(payload["saldoCaja"], "28.00")
        self.assertEqual(payload["inversionProductos"], "16.00")
        self.assertEqual(payload["inversionTotal"], "20.00")
        self.assertEqual(payload["fletesAsignados"], "4.00")
        self.assertEqual(payload["utilidadNeta"], "10.00")
        self.assertEqual(payload["rentabilidadNeta"], "50.00")
        self.assertEqual(payload["anio"], 2026)
        self.assertEqual(payload["vendidoAnio"], "30.00")
        self.assertEqual(payload["inversionAnio"], "20.00")
        self.assertEqual(payload["utilidadNetaAnio"], "10.00")
        self.assertEqual(payload["rentabilidadNetaAnio"], "50.00")
        self.assertEqual(payload["ordenesMes"], 1)
        self.assertEqual(len(payload["ordenes"]), 1)

    def test_dashboard_separates_freight_cash_date_from_profit_period(self):
        self.orden.fecha = date(2026, 4, 20)
        self.orden.save(update_fields=["fecha"])
        envio = Envio.objects.create(
            nombre="Abril pagado en mayo",
            estado=Envio.Estado.EN_TRANSITO,
            fecha_salida=date(2026, 4, 28),
            fecha_pago_flete=date(2026, 5, 3),
            periodo_utilidad=date(2026, 4, 1),
            costo_flete=Decimal("5.00"),
        )
        OrdenEnvio.objects.create(envio=envio, orden=self.orden, costo_flete_asignado=Decimal("5.00"))
        sincronizar_envio_caja(envio)

        abril = self.http.get(reverse("dashboard"), {"mes": "2026-04"}).context["dashboard_payload"]
        mayo = self.http.get(reverse("dashboard"), {"mes": "2026-05"}).context["dashboard_payload"]

        self.assertEqual(abril["fletesAsignados"], "5.00")
        self.assertEqual(abril["movimientoCaja"], "0.00")
        self.assertEqual(abril["utilidadNeta"], "9.00")
        self.assertEqual(abril["rentabilidadNeta"], "42.86")
        self.assertEqual(mayo["fletesAsignados"], "0.00")
        self.assertEqual(mayo["movimientoCaja"], "-5.00")
        self.assertEqual(mayo["egresosMes"], "5.00")
        self.assertEqual(mayo["utilidadNetaAnio"], "9.00")
        self.assertEqual(mayo["rentabilidadNetaAnio"], "42.86")

    def test_partial_and_full_payment_status(self):
        Pago.objects.create(orden=self.orden, fecha=date.today(), monto=Decimal("15.00"))
        self.assertFalse(self.orden.pagado_completo)
        self.assertEqual(self.orden.saldo_pendiente, Decimal("15.00"))
        Pago.objects.create(orden=self.orden, fecha=date.today(), monto=Decimal("15.00"))
        self.assertTrue(self.orden.pagado_completo)
        self.assertEqual(self.orden.saldo_pendiente, Decimal("0.00"))

    def test_payment_view_creates_cash_income(self):
        response = self.http.post(reverse("pago_agregar", args=[self.orden.pk]), {
            "fecha": date.today().isoformat(),
            "monto": "12.50",
            "metodo": "Zelle",
            "nota": "Inicial",
        })
        self.assertRedirects(response, self.orden.get_absolute_url())
        self.assertEqual(Pago.objects.count(), 1)
        movimiento = MovimientoCaja.objects.get()
        self.assertEqual(movimiento.tipo, MovimientoCaja.Tipo.INGRESO)
        self.assertEqual(movimiento.monto, Decimal("12.50"))

    def test_edit_payment_updates_cash_income(self):
        self.http.post(reverse("pago_agregar", args=[self.orden.pk]), {
            "fecha": date.today().isoformat(),
            "monto": "12.50",
            "metodo": "Zelle",
            "nota": "Inicial",
        })
        pago = Pago.objects.get()
        response = self.http.post(reverse("pago_editar", args=[pago.pk]), {
            "fecha": date.today().isoformat(),
            "monto": "18.75",
            "metodo": "Pago movil",
            "nota": "Ajustado",
        })
        self.assertRedirects(response, self.orden.get_absolute_url())
        pago.refresh_from_db()
        movimiento = pago.movimiento_caja
        self.assertEqual(pago.monto, Decimal("18.75"))
        self.assertEqual(movimiento.monto, Decimal("18.75"))
        self.assertEqual(movimiento.fecha, pago.fecha)
        self.assertIn("Orden", movimiento.descripcion)

    def test_delete_payment_deletes_cash_income(self):
        self.http.post(reverse("pago_agregar", args=[self.orden.pk]), {
            "fecha": date.today().isoformat(),
            "monto": "12.50",
            "metodo": "Zelle",
            "nota": "Inicial",
        })
        pago = Pago.objects.get()
        response = self.http.post(reverse("pago_eliminar", args=[pago.pk]))
        self.assertRedirects(response, self.orden.get_absolute_url())
        self.assertEqual(Pago.objects.count(), 0)
        self.assertEqual(MovimientoCaja.objects.count(), 0)

    def test_edit_manual_cash_movement(self):
        movimiento = MovimientoCaja.objects.create(
            fecha=date.today(),
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.DELIVERY,
            descripcion="Delivery",
            monto=Decimal("5.00"),
        )
        response = self.http.post(reverse("movimiento_editar", args=[movimiento.pk]), {
            "fecha": date.today().isoformat(),
            "tipo": MovimientoCaja.Tipo.EGRESO,
            "categoria": MovimientoCaja.Categoria.FLETE,
            "descripcion": "Flete ajustado",
            "monto": "8.25",
        })
        self.assertRedirects(response, reverse("caja"))
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.categoria, MovimientoCaja.Categoria.FLETE)
        self.assertEqual(movimiento.descripcion, "Flete ajustado")
        self.assertEqual(movimiento.monto, Decimal("8.25"))

    def test_delete_manual_cash_movement(self):
        movimiento = MovimientoCaja.objects.create(
            fecha=date.today(),
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.DELIVERY,
            descripcion="Delivery",
            monto=Decimal("5.00"),
        )
        response = self.http.post(reverse("movimiento_eliminar", args=[movimiento.pk]))
        self.assertRedirects(response, reverse("caja"))
        self.assertEqual(MovimientoCaja.objects.count(), 0)

    def test_payment_cash_movement_cannot_be_managed_from_cash(self):
        self.http.post(reverse("pago_agregar", args=[self.orden.pk]), {
            "fecha": date.today().isoformat(),
            "monto": "12.50",
            "metodo": "Zelle",
            "nota": "Inicial",
        })
        movimiento = MovimientoCaja.objects.get()
        edit_response = self.http.post(reverse("movimiento_editar", args=[movimiento.pk]), {
            "fecha": date.today().isoformat(),
            "tipo": MovimientoCaja.Tipo.EGRESO,
            "categoria": MovimientoCaja.Categoria.FLETE,
            "descripcion": "No debe cambiar",
            "monto": "8.25",
        })
        delete_response = self.http.post(reverse("movimiento_eliminar", args=[movimiento.pk]))
        movimiento.refresh_from_db()
        self.assertRedirects(edit_response, reverse("caja"))
        self.assertRedirects(delete_response, reverse("caja"))
        self.assertEqual(MovimientoCaja.objects.count(), 1)
        self.assertEqual(movimiento.tipo, MovimientoCaja.Tipo.INGRESO)
        self.assertEqual(movimiento.monto, Decimal("12.50"))

    def test_cash_payload_includes_rolling_balance_for_selected_range(self):
        MovimientoCaja.objects.create(
            fecha=date(2026, 1, 31),
            tipo=MovimientoCaja.Tipo.INGRESO,
            categoria=MovimientoCaja.Categoria.OTRO,
            descripcion="Saldo enero",
            monto=Decimal("20.00"),
        )
        MovimientoCaja.objects.create(
            fecha=date(2026, 2, 10),
            tipo=MovimientoCaja.Tipo.INGRESO,
            categoria=MovimientoCaja.Categoria.COBRO_CLIENTE,
            descripcion="Ingreso febrero",
            monto=Decimal("12.00"),
        )
        MovimientoCaja.objects.create(
            fecha=date(2026, 2, 11),
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.FLETE,
            descripcion="Egreso febrero",
            monto=Decimal("4.00"),
        )
        response = self.http.get(reverse("caja"), {"desde": "2026-02-01", "hasta": "2026-02-28"})
        payload = response.context["caja_payload"]
        self.assertEqual(payload["saldoInicial"], "20.00")
        self.assertEqual(payload["movimientoPeriodo"], "8.00")
        self.assertEqual(payload["saldoFinal"], "28.00")

    def test_shipment_form_formats_order_money_with_two_decimals(self):
        self.orden.estado = Orden.Estado.COMPRADA
        self.orden.save(update_fields=["estado"])
        response = self.http.get(reverse("envio_crear"))
        content = response.content.decode("utf-8")
        self.assertIn("USD 30.00", content)
        self.assertIn("USD 14.00", content)
        self.assertNotIn("30.000000", content)

    def test_create_shipment_assigns_freight_and_cash_expense(self):
        self.orden.estado = Orden.Estado.COMPRADA
        self.orden.save(update_fields=["estado"])
        segunda = Orden.objects.create(
            cliente=self.cliente,
            estado=Orden.Estado.COMPRADA,
            inicial_sugerida=Decimal("0.00"),
        )
        ItemPedido.objects.create(
            orden=segunda,
            descripcion="Short",
            precio_final=Decimal("8.00"),
            costo_estimado=Decimal("4.00"),
        )

        response = self.http.post(reverse("envio_crear"), {
            "nombre": "Miami lote 1",
            "estado": Envio.Estado.EN_TRANSITO,
            "courier": "Courier test",
            "fecha_salida": date.today().isoformat(),
            "fecha_llegada": "",
            "fecha_pago_flete": date.today().isoformat(),
            "periodo_utilidad": date.today().strftime("%Y-%m"),
            "costo_flete": "10.00",
            "notas": "",
            "ordenes": [str(self.orden.pk), str(segunda.pk)],
        })

        envio = Envio.objects.get()
        self.assertRedirects(response, envio.get_absolute_url())
        self.assertEqual(OrdenEnvio.objects.count(), 2)
        self.orden.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_TRANSITO)
        self.assertEqual(segunda.estado, Orden.Estado.EN_TRANSITO)
        self.assertEqual(self.orden.flete_asignado, Decimal("8.00"))
        self.assertEqual(segunda.flete_asignado, Decimal("2.00"))
        self.assertEqual(self.orden.utilidad_real_neta, Decimal("6.00"))
        movimiento = envio.movimiento_caja
        self.assertEqual(movimiento.tipo, MovimientoCaja.Tipo.EGRESO)
        self.assertEqual(movimiento.categoria, MovimientoCaja.Categoria.FLETE)
        self.assertEqual(movimiento.monto, Decimal("10.00"))
        self.assertEqual(movimiento.fecha, date.today())

    def test_shipment_cash_movement_cannot_be_managed_from_cash(self):
        envio = Envio.objects.create(nombre="Miami lote 2", costo_flete=Decimal("7.00"))
        movimiento = MovimientoCaja.objects.create(
            fecha=date.today(),
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.FLETE,
            descripcion="Flete Miami lote 2",
            monto=Decimal("7.00"),
        )
        envio.movimiento_caja = movimiento
        envio.save(update_fields=["movimiento_caja"])

        edit_response = self.http.post(reverse("movimiento_editar", args=[movimiento.pk]), {
            "fecha": date.today().isoformat(),
            "tipo": MovimientoCaja.Tipo.INGRESO,
            "categoria": MovimientoCaja.Categoria.OTRO,
            "descripcion": "No debe cambiar",
            "monto": "100.00",
        })
        delete_response = self.http.post(reverse("movimiento_eliminar", args=[movimiento.pk]))
        movimiento.refresh_from_db()
        self.assertRedirects(edit_response, reverse("caja"))
        self.assertRedirects(delete_response, reverse("caja"))
        self.assertEqual(MovimientoCaja.objects.count(), 1)
        self.assertEqual(movimiento.tipo, MovimientoCaja.Tipo.EGRESO)
        self.assertEqual(movimiento.monto, Decimal("7.00"))

    def test_change_shipment_status_syncs_orders_to_received(self):
        self.orden.estado = Orden.Estado.EN_TRANSITO
        self.orden.save(update_fields=["estado"])
        envio = Envio.objects.create(nombre="Miami lote 3", estado=Envio.Estado.EN_TRANSITO)
        OrdenEnvio.objects.create(envio=envio, orden=self.orden, costo_flete_asignado=Decimal("0.00"))

        response = self.http.post(
            reverse("envio_cambiar_estado", args=[envio.pk]),
            data='{"estado":"recibido"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["estado"], Envio.Estado.RECIBIDO)
        self.assertEqual(payload["ordenesActualizadas"], 1)
        envio.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertIsNotNone(envio.fecha_llegada)
        self.assertEqual(self.orden.estado, Orden.Estado.ENTREGADA)

    def test_change_shipment_status_ignores_cancelled_orders(self):
        self.orden.estado = Orden.Estado.CANCELADA
        self.orden.save(update_fields=["estado"])
        envio = Envio.objects.create(nombre="Miami lote 4", estado=Envio.Estado.PREPARANDO)
        OrdenEnvio.objects.create(envio=envio, orden=self.orden, costo_flete_asignado=Decimal("0.00"))

        response = self.http.post(
            reverse("envio_cambiar_estado", args=[envio.pk]),
            data='{"estado":"en_transito"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["ordenesActualizadas"], 0)
        envio.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertIsNotNone(envio.fecha_salida)
        self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

    def test_edit_shipment_updates_dates_cash_and_freight_distribution(self):
        self.orden.estado = Orden.Estado.EN_TRANSITO
        self.orden.save(update_fields=["estado"])
        segunda = Orden.objects.create(cliente=self.cliente, estado=Orden.Estado.EN_TRANSITO)
        ItemPedido.objects.create(
            orden=segunda,
            descripcion="Producto dos",
            precio_final=Decimal("8.00"),
            costo_estimado=Decimal("4.00"),
        )
        envio = Envio.objects.create(
            nombre="Miami historico",
            estado=Envio.Estado.EN_TRANSITO,
            fecha_salida=date(2026, 5, 16),
            fecha_pago_flete=date(2026, 5, 16),
            periodo_utilidad=date(2026, 5, 1),
            costo_flete=Decimal("10.00"),
        )
        OrdenEnvio.objects.create(envio=envio, orden=self.orden, costo_flete_asignado=Decimal("8.00"))
        OrdenEnvio.objects.create(envio=envio, orden=segunda, costo_flete_asignado=Decimal("2.00"))
        movimiento = MovimientoCaja.objects.create(
            fecha=date(2026, 5, 16),
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.FLETE,
            descripcion="Flete Miami historico",
            monto=Decimal("10.00"),
        )
        envio.movimiento_caja = movimiento
        envio.save(update_fields=["movimiento_caja"])

        response = self.http.post(reverse("envio_editar", args=[envio.pk]), {
            "nombre": "Miami historico",
            "estado": Envio.Estado.RECIBIDO,
            "courier": "South Cargo",
            "fecha_salida": "2026-03-05",
            "fecha_llegada": "2026-03-18",
            "fecha_pago_flete": "2026-05-16",
            "periodo_utilidad": "2026-03",
            "costo_flete": "20.00",
            "notas": "Corregido",
        })

        self.assertRedirects(response, envio.get_absolute_url())
        envio.refresh_from_db()
        movimiento.refresh_from_db()
        self.orden.refresh_from_db()
        segunda.refresh_from_db()
        primera_relacion = self.orden.envio_asignado
        segunda_relacion = segunda.envio_asignado
        self.assertEqual(envio.fecha_salida, date(2026, 3, 5))
        self.assertEqual(envio.fecha_llegada, date(2026, 3, 18))
        self.assertEqual(envio.fecha_pago_flete, date(2026, 5, 16))
        self.assertEqual(envio.periodo_utilidad, date(2026, 3, 1))
        self.assertEqual(envio.costo_flete, Decimal("20.00"))
        self.assertEqual(movimiento.fecha, date(2026, 5, 16))
        self.assertEqual(movimiento.monto, Decimal("20.00"))
        self.assertEqual(primera_relacion.costo_flete_asignado, Decimal("16.00"))
        self.assertEqual(segunda_relacion.costo_flete_asignado, Decimal("4.00"))
        self.assertEqual(self.orden.estado, Orden.Estado.ENTREGADA)
        self.assertEqual(segunda.estado, Orden.Estado.ENTREGADA)

    def test_edit_item_updates_order_totals(self):
        item = self.orden.items.first()
        response = self.http.post(reverse("item_editar", args=[item.pk]), {
            "imagen_url": "",
            "link": "",
            "tienda": ItemPedido.Tienda.SHEIN,
            "sku": "editado",
            "descripcion": "Producto editado",
            "precio_final": "40.00",
            "costo_estimado": "20.00",
            "costo_real": "",
            "precio_shein_eeuu": "",
            "precio_shein_espana": "",
            "precio_shein_venezuela": "",
            "precio_shein_colombia": "",
            "proveedor_version": ItemPedido.VersionProveedor.EEUU,
        })
        self.assertRedirects(response, self.orden.get_absolute_url())
        item.refresh_from_db()
        self.assertEqual(item.descripcion, "Producto editado")
        self.assertEqual(item.precio_final, Decimal("40.00"))
        self.assertEqual(self.orden.total_final, Decimal("50.00"))
        self.assertEqual(self.orden.ganancia_estimada, Decimal("25.00"))

    def test_delete_item_updates_order_totals_without_touching_payments(self):
        Pago.objects.create(orden=self.orden, fecha=date.today(), monto=Decimal("5.00"))
        item = self.orden.items.first()
        response = self.http.post(reverse("item_eliminar", args=[item.pk]))
        self.assertRedirects(response, self.orden.get_absolute_url())
        self.assertEqual(ItemPedido.objects.count(), 1)
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(self.orden.total_final, Decimal("10.00"))
        self.assertEqual(self.orden.saldo_pendiente, Decimal("5.00"))

    def test_client_report_pdf_hides_internal_costs(self):
        response = self.http.get(reverse("reporte_cliente_pdf", args=[self.orden.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        content = b"".join(response.streaming_content)
        self.assertIn(b"Pedido", content)
        self.assertNotIn(b"costo_estimado", content)
        self.assertNotIn(b"costo_real", content)
        self.assertNotIn(b"Ganancia", content)
        self.assertNotIn(b"Shein EEUU", content)
