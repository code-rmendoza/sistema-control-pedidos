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

    def test_client_report_pdf_hides_internal_costs(self):
        response = self.http.get(reverse("reporte_cliente_pdf", args=[self.orden.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

# Create your tests here.
