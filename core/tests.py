from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as HttpClient
from django.test import TestCase
from django.urls import reverse

from .models import Cliente, ItemPedido, MovimientoCaja, Orden, Pago


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

# Create your tests here.
