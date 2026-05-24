from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone


class Cliente(models.Model):
    nombre = models.CharField(max_length=160)
    telefono = models.CharField(max_length=60, blank=True)
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("cliente_detalle", args=[self.pk])


class Orden(models.Model):
    class Estado(models.TextChoices):
        COTIZADA = "cotizada", "Cotizada"
        PENDIENTE_COMPRA = "pendiente_compra", "Pedido pendiente de compra"
        COMPRADA = "comprada", "Comprada"
        EN_TRANSITO = "en_transito", "En transito"
        ENTREGADA = "entregada", "Entregada"
        CANCELADA = "cancelada", "Cancelada"

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="ordenes")
    estado = models.CharField(max_length=32, choices=Estado.choices, default=Estado.COTIZADA)
    fecha = models.DateField(default=timezone.localdate)
    inicial_sugerida = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"Orden #{self.pk} - {self.cliente}"

    def get_absolute_url(self):
        return reverse("orden_detalle", args=[self.pk])

    @property
    def total_final(self):
        return self.items.aggregate(total=Sum("precio_final"))["total"] or Decimal("0.00")

    @property
    def total_pagado(self):
        return self.pagos.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")

    @property
    def saldo_pendiente(self):
        saldo = self.total_final - self.total_pagado
        return max(saldo, Decimal("0.00"))

    @property
    def pagado_completo(self):
        return self.total_final > 0 and self.total_pagado >= self.total_final

    @property
    def ganancia_estimada(self):
        return sum((item.ganancia_estimada for item in self.items.all()), Decimal("0.00"))

    @property
    def ganancia_real(self):
        return sum((item.ganancia_real for item in self.items.all()), Decimal("0.00"))

    @property
    def flete_asignado(self):
        try:
            return self.envio_asignado.costo_flete_asignado
        except OrdenEnvio.DoesNotExist:
            return Decimal("0.00")

    @property
    def utilidad_real_neta(self):
        return self.ganancia_real - self.flete_asignado

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and self.inicial_sugerida == Decimal("0.00"):
            self.inicial_sugerida = (self.total_final * Decimal("0.50")).quantize(Decimal("0.01"))
            super().save(update_fields=["inicial_sugerida"])


class ItemPedido(models.Model):
    class Tienda(models.TextChoices):
        SHEIN = "shein", "Shein"
        AMAZON = "amazon", "Amazon"
        ALIEXPRESS = "aliexpress", "AliExpress"
        OTRO = "otro", "Otro"

    class VersionProveedor(models.TextChoices):
        EEUU = "eeuu", "EEUU"
        ESPANA = "espana", "Espana"
        VENEZUELA = "venezuela", "Venezuela"
        COLOMBIA = "colombia", "Colombia"
        OTRO = "otro", "Otro"

    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name="items")
    imagen = models.ImageField(upload_to="items/", blank=True)
    imagen_url = models.URLField(max_length=1000, blank=True)
    link = models.URLField(max_length=1000, blank=True)
    tienda = models.CharField(max_length=32, choices=Tienda.choices, default=Tienda.SHEIN)
    sku = models.CharField(max_length=120, blank=True, db_index=True)
    descripcion = models.CharField(max_length=240)
    precio_final = models.DecimalField(max_digits=10, decimal_places=2)
    costo_estimado = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    costo_real = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_shein_eeuu = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_shein_espana = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_shein_venezuela = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_shein_colombia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    proveedor_version = models.CharField(max_length=32, choices=VersionProveedor.choices, default=VersionProveedor.EEUU)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.descripcion

    @property
    def costo_para_real(self):
        return self.costo_real if self.costo_real is not None else self.costo_estimado

    @property
    def ganancia_estimada(self):
        return self.precio_final - self.costo_estimado

    @property
    def ganancia_real(self):
        return self.precio_final - self.costo_para_real

    @property
    def rentabilidad_estimada(self):
        if self.costo_estimado <= 0:
            return None
        return (self.ganancia_estimada / self.costo_estimado * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def rentabilidad_real(self):
        costo = self.costo_para_real
        if costo <= 0:
            return None
        return (self.ganancia_real / costo * Decimal("100")).quantize(Decimal("0.01"))


class PrecioReferencia(models.Model):
    item = models.OneToOneField(ItemPedido, on_delete=models.CASCADE, related_name="precios_referencia")
    shein_eeuu = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shein_espana = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shein_venezuela = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shein_colombia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Referencias de {self.item}"


class Pago(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name="pagos")
    fecha = models.DateField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=80, blank=True)
    nota = models.CharField(max_length=200, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"${self.monto} - {self.orden}"


class MovimientoCaja(models.Model):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    class Categoria(models.TextChoices):
        COBRO_CLIENTE = "cobro_cliente", "Cobro a cliente"
        PROVEEDOR = "proveedor", "Pago a proveedores"
        SUELDO = "sueldo", "Sueldo"
        GASOLINA = "gasolina", "Gasolina"
        DELIVERY = "delivery", "Delivery"
        FLETE = "flete", "Flete"
        OTRO = "otro", "Otro"

    fecha = models.DateField()
    tipo = models.CharField(max_length=16, choices=Tipo.choices)
    categoria = models.CharField(max_length=32, choices=Categoria.choices, default=Categoria.OTRO)
    descripcion = models.CharField(max_length=220)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    pago = models.OneToOneField(Pago, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimiento_caja")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.monto} - {self.descripcion}"


class Envio(models.Model):
    class Estado(models.TextChoices):
        PREPARANDO = "preparando", "Preparando"
        EN_TRANSITO = "en_transito", "En transito"
        RECIBIDO = "recibido", "Recibido"
        CERRADO = "cerrado", "Cerrado"

    nombre = models.CharField(max_length=160)
    estado = models.CharField(max_length=32, choices=Estado.choices, default=Estado.PREPARANDO)
    courier = models.CharField(max_length=120, blank=True)
    fecha_creado = models.DateTimeField(auto_now_add=True)
    fecha_salida = models.DateField(null=True, blank=True)
    fecha_llegada = models.DateField(null=True, blank=True)
    fecha_pago_flete = models.DateField(null=True, blank=True)
    periodo_utilidad = models.DateField(default=timezone.localdate)
    costo_flete = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    notas = models.TextField(blank=True)
    movimiento_caja = models.OneToOneField(
        MovimientoCaja,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envio",
    )

    class Meta:
        ordering = ["-fecha_creado", "-id"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if self.periodo_utilidad:
            self.periodo_utilidad = self.periodo_utilidad.replace(day=1)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("envio_detalle", args=[self.pk])

    @property
    def total_vendido(self):
        return sum((relacion.orden.total_final for relacion in self.ordenes_envio.all()), Decimal("0.00"))

    @property
    def costo_productos(self):
        total = Decimal("0.00")
        for relacion in self.ordenes_envio.all():
            total += sum((item.costo_para_real for item in relacion.orden.items.all()), Decimal("0.00"))
        return total

    @property
    def utilidad_neta(self):
        return self.total_vendido - self.costo_productos - self.costo_flete


class OrdenEnvio(models.Model):
    envio = models.ForeignKey(Envio, on_delete=models.CASCADE, related_name="ordenes_envio")
    orden = models.OneToOneField(Orden, on_delete=models.PROTECT, related_name="envio_asignado")
    costo_flete_asignado = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["orden_id"]

    def __str__(self):
        return f"{self.envio} - Orden #{self.orden_id}"
