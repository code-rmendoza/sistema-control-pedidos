from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from core.models import MovimientoCaja


def total_movimientos(movimientos_qs):
    ingresos = movimientos_qs.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    egresos = movimientos_qs.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    return ingresos, egresos, ingresos - egresos


def sincronizar_pago_caja(pago):
    descripcion = f"Cobro a {pago.orden.cliente.nombre} - Orden #{pago.orden.pk}"
    movimiento, _created = MovimientoCaja.objects.get_or_create(
        pago=pago,
        defaults={
            "fecha": pago.fecha,
            "tipo": MovimientoCaja.Tipo.INGRESO,
            "categoria": MovimientoCaja.Categoria.COBRO_CLIENTE,
            "descripcion": descripcion,
            "monto": pago.monto,
        },
    )
    movimiento.fecha = pago.fecha
    movimiento.tipo = MovimientoCaja.Tipo.INGRESO
    movimiento.categoria = MovimientoCaja.Categoria.COBRO_CLIENTE
    movimiento.descripcion = descripcion
    movimiento.monto = pago.monto
    movimiento.save(update_fields=["fecha", "tipo", "categoria", "descripcion", "monto"])
    return movimiento


def sincronizar_envio_caja(envio):
    if envio.costo_flete <= 0:
        if envio.movimiento_caja_id:
            envio.movimiento_caja.delete()
            envio.movimiento_caja = None
            envio.save(update_fields=["movimiento_caja"])
        return None

    descripcion = f"Flete {envio.nombre}"
    fecha_movimiento = envio.fecha_pago_flete or envio.fecha_salida or timezone.localdate()
    movimiento = envio.movimiento_caja
    if movimiento is None:
        movimiento = MovimientoCaja.objects.create(
            fecha=fecha_movimiento,
            tipo=MovimientoCaja.Tipo.EGRESO,
            categoria=MovimientoCaja.Categoria.FLETE,
            descripcion=descripcion,
            monto=envio.costo_flete,
        )
        envio.movimiento_caja = movimiento
        envio.save(update_fields=["movimiento_caja"])
    else:
        movimiento.fecha = fecha_movimiento
        movimiento.tipo = MovimientoCaja.Tipo.EGRESO
        movimiento.categoria = MovimientoCaja.Categoria.FLETE
        movimiento.descripcion = descripcion
        movimiento.monto = envio.costo_flete
        movimiento.save(update_fields=["fecha", "tipo", "categoria", "descripcion", "monto"])
    return movimiento
