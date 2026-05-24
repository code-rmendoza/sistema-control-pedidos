from decimal import Decimal

from core.models import Envio, Orden
from core.utils import money


def costo_productos_orden(orden):
    return sum((item.costo_para_real for item in orden.items.all()), Decimal("0.00"))


def repartir_flete(ordenes, costo_flete):
    costo_flete = money(costo_flete).quantize(Decimal("0.01"))
    if not ordenes or costo_flete <= 0:
        return {orden.id: Decimal("0.00") for orden in ordenes}

    bases = {orden.id: costo_productos_orden(orden) for orden in ordenes}
    base_total = sum(bases.values(), Decimal("0.00"))
    asignaciones = {}
    acumulado = Decimal("0.00")
    for orden in ordenes[:-1]:
        if base_total > 0:
            asignado = (costo_flete * bases[orden.id] / base_total).quantize(Decimal("0.01"))
        else:
            asignado = (costo_flete / len(ordenes)).quantize(Decimal("0.01"))
        asignaciones[orden.id] = asignado
        acumulado += asignado
    asignaciones[ordenes[-1].id] = costo_flete - acumulado
    return asignaciones


def sincronizar_estado_ordenes_envio(envio):
    if envio.estado not in {Envio.Estado.EN_TRANSITO, Envio.Estado.RECIBIDO}:
        return 0
    nuevo_estado = Orden.Estado.EN_TRANSITO if envio.estado == Envio.Estado.EN_TRANSITO else Orden.Estado.ENTREGADA
    ordenes = [
        relacion.orden
        for relacion in envio.ordenes_envio.select_related("orden")
        if relacion.orden.estado != Orden.Estado.CANCELADA
    ]
    for orden in ordenes:
        orden.estado = nuevo_estado
        orden.save(update_fields=["estado", "actualizado"])
    return len(ordenes)


def recalcular_flete_envio(envio):
    relaciones = list(envio.ordenes_envio.select_related("orden").prefetch_related("orden__items"))
    ordenes = [relacion.orden for relacion in relaciones]
    asignaciones = repartir_flete(ordenes, envio.costo_flete)
    for relacion in relaciones:
        relacion.costo_flete_asignado = asignaciones[relacion.orden_id]
        relacion.save(update_fields=["costo_flete_asignado"])
