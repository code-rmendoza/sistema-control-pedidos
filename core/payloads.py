from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse

from .models import Cliente, Envio, MovimientoCaja, Orden, Pago
from .services.caja import total_movimientos
from .utils import decimal_payload, selected_month_range


def orden_payload(orden):
    return {
        "id": orden.id,
        "cliente": orden.cliente.nombre,
        "fecha": orden.fecha.isoformat(),
        "fechaDisplay": orden.fecha.strftime("%d/%m/%Y"),
        "estado": orden.estado,
        "estadoDisplay": orden.get_estado_display(),
        "totalFinal": decimal_payload(orden.total_final),
        "totalPagado": decimal_payload(orden.total_pagado),
        "saldoPendiente": decimal_payload(orden.saldo_pendiente),
        "fleteAsignado": decimal_payload(orden.flete_asignado),
        "utilidadRealNeta": decimal_payload(orden.utilidad_real_neta),
        "pagadoCompleto": orden.pagado_completo,
        "itemsCount": orden.items.count(),
        "url": orden.get_absolute_url(),
    }


def envio_payload(envio):
    ordenes_envio = list(envio.ordenes_envio.select_related("orden__cliente").prefetch_related("orden__items", "orden__pagos"))
    return {
        "id": envio.id,
        "nombre": envio.nombre,
        "estado": envio.estado,
        "estadoDisplay": envio.get_estado_display(),
        "courier": envio.courier or "",
        "fechaCreadoDisplay": envio.fecha_creado.strftime("%d/%m/%Y"),
        "fechaSalida": envio.fecha_salida.isoformat() if envio.fecha_salida else "",
        "fechaSalidaDisplay": envio.fecha_salida.strftime("%d/%m/%Y") if envio.fecha_salida else "-",
        "fechaLlegadaDisplay": envio.fecha_llegada.strftime("%d/%m/%Y") if envio.fecha_llegada else "-",
        "fechaPagoFleteDisplay": envio.fecha_pago_flete.strftime("%d/%m/%Y") if envio.fecha_pago_flete else "-",
        "periodoUtilidad": envio.periodo_utilidad.isoformat() if envio.periodo_utilidad else "",
        "periodoUtilidadDisplay": envio.periodo_utilidad.strftime("%m/%Y") if envio.periodo_utilidad else "-",
        "costoFlete": decimal_payload(envio.costo_flete),
        "totalVendido": decimal_payload(envio.total_vendido),
        "costoProductos": decimal_payload(envio.costo_productos),
        "utilidadNeta": decimal_payload(envio.utilidad_neta),
        "ordenesCount": len(ordenes_envio),
        "url": envio.get_absolute_url(),
        "urls": {
            "editar": reverse("envio_editar", args=[envio.id]),
            "cambiarEstado": reverse("envio_cambiar_estado", args=[envio.id]),
        },
        "estados": [
            {"value": value, "label": label}
            for value, label in Envio.Estado.choices
        ],
        "ordenes": [
            {
                **orden_payload(relacion.orden),
                "fleteAsignado": decimal_payload(relacion.costo_flete_asignado),
            }
            for relacion in ordenes_envio
        ],
    }


def orden_envio_form_payload(orden):
    return {
        "id": orden.id,
        "cliente": orden.cliente.nombre,
        "totalFinal": decimal_payload(orden.total_final),
        "gananciaReal": decimal_payload(orden.ganancia_real),
    }


def item_payload(item):
    imagen = ""
    if item.imagen:
        try:
            imagen = item.imagen.url
        except ValueError:
            imagen = ""
    return {
        "id": item.id,
        "descripcion": item.descripcion,
        "sku": item.sku or "",
        "imagen": imagen or item.imagen_url,
        "link": item.link,
        "urls": {
            "editar": reverse("item_editar", args=[item.id]),
            "eliminar": reverse("item_eliminar", args=[item.id]),
        },
        "tienda": item.get_tienda_display(),
        "proveedorVersion": item.get_proveedor_version_display(),
        "precioFinal": decimal_payload(item.precio_final),
        "costoEstimado": decimal_payload(item.costo_estimado),
        "costoReal": decimal_payload(item.costo_real) if item.costo_real is not None else "",
        "rentabilidadReal": str(item.rentabilidad_real) if item.rentabilidad_real is not None else "",
        "referencias": {
            "EEUU": decimal_payload(item.precio_shein_eeuu) if item.precio_shein_eeuu is not None else "",
            "Espana": decimal_payload(item.precio_shein_espana) if item.precio_shein_espana is not None else "",
            "Venezuela": decimal_payload(item.precio_shein_venezuela) if item.precio_shein_venezuela is not None else "",
            "Colombia": decimal_payload(item.precio_shein_colombia) if item.precio_shein_colombia is not None else "",
        },
    }


def pago_payload(pago):
    return {
        "id": pago.id,
        "fecha": pago.fecha.isoformat(),
        "fechaDisplay": pago.fecha.strftime("%d/%m/%Y"),
        "monto": decimal_payload(pago.monto),
        "metodo": pago.metodo or "",
        "nota": pago.nota or "",
        "urls": {
            "editar": reverse("pago_editar", args=[pago.id]),
            "eliminar": reverse("pago_eliminar", args=[pago.id]),
        },
    }


def movimiento_payload(movimiento):
    es_envio = hasattr(movimiento, "envio")
    editable = movimiento.pago_id is None and not es_envio
    return {
        "id": movimiento.id,
        "fecha": movimiento.fecha.isoformat(),
        "fechaDisplay": movimiento.fecha.strftime("%d/%m/%Y"),
        "tipo": movimiento.tipo,
        "tipoDisplay": movimiento.get_tipo_display(),
        "categoria": movimiento.categoria,
        "categoriaDisplay": movimiento.get_categoria_display(),
        "descripcion": movimiento.descripcion,
        "monto": decimal_payload(movimiento.monto),
        "esPago": movimiento.pago_id is not None,
        "esEnvio": es_envio,
        "editable": editable,
        "origen": "Pago de orden" if movimiento.pago_id is not None else ("Flete de envio" if es_envio else "Manual"),
        "urls": {
            "editar": reverse("movimiento_editar", args=[movimiento.id]) if editable else "",
            "eliminar": reverse("movimiento_eliminar", args=[movimiento.id]) if editable else "",
        },
    }


def cliente_payload(cliente):
    ordenes = list(cliente.ordenes.all())
    total_vendido = sum((orden.total_final for orden in ordenes), Decimal("0.00"))
    saldo_pendiente = sum((orden.saldo_pendiente for orden in ordenes), Decimal("0.00"))
    return {
        "id": cliente.id,
        "nombre": cliente.nombre,
        "telefono": cliente.telefono or "",
        "notas": cliente.notas or "",
        "creado": cliente.creado.isoformat(),
        "creadoDisplay": cliente.creado.strftime("%d/%m/%Y"),
        "ordenesCount": len(ordenes),
        "totalVendido": decimal_payload(total_vendido),
        "saldoPendiente": decimal_payload(saldo_pendiente),
        "url": cliente.get_absolute_url(),
    }


def cliente_detalle_payload(cliente):
    ordenes = list(cliente.ordenes.prefetch_related("items", "pagos").all())
    total_vendido = sum((orden.total_final for orden in ordenes), Decimal("0.00"))
    total_pagado = sum((orden.total_pagado for orden in ordenes), Decimal("0.00"))
    saldo_pendiente = sum((orden.saldo_pendiente for orden in ordenes), Decimal("0.00"))
    return {
        **cliente_payload(cliente),
        "totalPagado": decimal_payload(total_pagado),
        "totalVendido": decimal_payload(total_vendido),
        "saldoPendiente": decimal_payload(saldo_pendiente),
        "urls": {
            "clientes": reverse("clientes"),
            "nuevaOrden": reverse("orden_crear"),
        },
        "ordenes": [orden_payload(orden) for orden in ordenes],
    }


def orden_detalle_payload(orden, csrf_token):
    return {
        **orden_payload(orden),
        "clienteUrl": orden.cliente.get_absolute_url(),
        "csrfToken": csrf_token,
        "inicialSugerida": decimal_payload(orden.inicial_sugerida),
        "gananciaEstimada": decimal_payload(orden.ganancia_estimada),
        "gananciaReal": decimal_payload(orden.ganancia_real),
        "fleteAsignado": decimal_payload(orden.flete_asignado),
        "utilidadRealNeta": decimal_payload(orden.utilidad_real_neta),
        "envio": (
            {
                "nombre": orden.envio_asignado.envio.nombre,
                "url": orden.envio_asignado.envio.get_absolute_url(),
            }
            if hasattr(orden, "envio_asignado")
            else None
        ),
        "notas": orden.notas,
        "urls": {
            "editar": reverse("orden_editar", args=[orden.id]),
            "pdf": reverse("reporte_cliente_pdf", args=[orden.id]),
            "ordenes": reverse("ordenes"),
            "cambiarEstado": reverse("orden_cambiar_estado", args=[orden.id]),
        },
        "estados": [
            {"value": value, "label": label}
            for value, label in Orden.Estado.choices
        ],
        "items": [item_payload(item) for item in orden.items.all()],
        "pagos": [pago_payload(pago) for pago in orden.pagos.all()],
    }


def dashboard_context(request):
    selected_month, first_day, last_day = selected_month_range(request)
    first_day_year = date(first_day.year, 1, 1)
    last_day_year = date(first_day.year, 12, 31)
    pagos_mes = Pago.objects.filter(fecha__range=(first_day, last_day)).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    movimientos_anteriores = MovimientoCaja.objects.filter(fecha__lt=first_day)
    movimientos_mes = MovimientoCaja.objects.filter(fecha__range=(first_day, last_day))
    _ingresos_anteriores, _egresos_anteriores, saldo_inicial_caja = total_movimientos(movimientos_anteriores)
    ingresos_mes, egresos_mes, movimiento_caja_mes = total_movimientos(movimientos_mes)
    saldo_final_caja = saldo_inicial_caja + movimiento_caja_mes
    ordenes_mes_qs = (
        Orden.objects.filter(fecha__range=(first_day, last_day))
        .select_related("cliente")
        .prefetch_related("items", "pagos", "envio_asignado")
    )
    ordenes_mes = list(ordenes_mes_qs)
    ordenes_mes_activas = [
        orden
        for orden in ordenes_mes
        if orden.estado not in {Orden.Estado.ENTREGADA, Orden.Estado.CANCELADA}
    ]
    vendido_mes = sum((orden.total_final for orden in ordenes_mes), Decimal("0.00"))
    pendientes = sum((orden.saldo_pendiente for orden in ordenes_mes), Decimal("0.00"))
    ganancia_estimada = sum((orden.ganancia_estimada for orden in ordenes_mes), Decimal("0.00"))
    ganancia_real = sum((orden.ganancia_real for orden in ordenes_mes), Decimal("0.00"))
    inversion_productos = sum(
        (
            sum((item.costo_para_real for item in orden.items.all()), Decimal("0.00"))
            for orden in ordenes_mes
        ),
        Decimal("0.00"),
    )
    fletes_asignados = sum(
        (envio.costo_flete for envio in Envio.objects.filter(periodo_utilidad__range=(first_day, last_day))),
        Decimal("0.00"),
    )
    inversion_total = inversion_productos + fletes_asignados
    utilidad_neta = ganancia_real - fletes_asignados
    rentabilidad_neta = (utilidad_neta / inversion_total * Decimal("100.00")) if inversion_total else Decimal("0.00")
    ordenes_anio = list(
        Orden.objects.filter(fecha__range=(first_day_year, last_day_year))
        .prefetch_related("items")
    )
    vendido_anio = sum((orden.total_final for orden in ordenes_anio), Decimal("0.00"))
    ganancia_real_anio = sum((orden.ganancia_real for orden in ordenes_anio), Decimal("0.00"))
    inversion_productos_anio = sum(
        (
            sum((item.costo_para_real for item in orden.items.all()), Decimal("0.00"))
            for orden in ordenes_anio
        ),
        Decimal("0.00"),
    )
    fletes_asignados_anio = sum(
        (envio.costo_flete for envio in Envio.objects.filter(periodo_utilidad__range=(first_day_year, last_day_year))),
        Decimal("0.00"),
    )
    inversion_total_anio = inversion_productos_anio + fletes_asignados_anio
    utilidad_neta_anio = ganancia_real_anio - fletes_asignados_anio
    rentabilidad_neta_anio = (
        utilidad_neta_anio / inversion_total_anio * Decimal("100.00")
    ) if inversion_total_anio else Decimal("0.00")
    dashboard_payload = {
        "mes": selected_month,
        "mesLabel": first_day.strftime("%m/%Y"),
        "anio": first_day.year,
        "ordenesMes": len(ordenes_mes),
        "pedidosActivos": len(ordenes_mes_activas),
        "vendidoMes": decimal_payload(vendido_mes),
        "cobradoMes": decimal_payload(pagos_mes),
        "egresosMes": decimal_payload(egresos_mes),
        "saldoInicialCaja": decimal_payload(saldo_inicial_caja),
        "movimientoCaja": decimal_payload(movimiento_caja_mes),
        "saldoCaja": decimal_payload(saldo_final_caja),
        "pendienteCobrar": decimal_payload(pendientes),
        "inversionProductos": decimal_payload(inversion_productos),
        "inversionTotal": decimal_payload(inversion_total),
        "gananciaEstimada": decimal_payload(ganancia_estimada),
        "gananciaReal": decimal_payload(ganancia_real),
        "fletesAsignados": decimal_payload(fletes_asignados),
        "utilidadNeta": decimal_payload(utilidad_neta),
        "rentabilidadNeta": decimal_payload(rentabilidad_neta),
        "vendidoAnio": decimal_payload(vendido_anio),
        "inversionAnio": decimal_payload(inversion_total_anio),
        "gananciaRealAnio": decimal_payload(ganancia_real_anio),
        "fletesAnio": decimal_payload(fletes_asignados_anio),
        "utilidadNetaAnio": decimal_payload(utilidad_neta_anio),
        "rentabilidadNetaAnio": decimal_payload(rentabilidad_neta_anio),
        "urls": {
            "nuevaOrden": reverse("orden_crear"),
            "ordenes": reverse("ordenes"),
            "envios": reverse("envios"),
        },
        "ordenes": [
            orden_payload(orden)
            for orden in ordenes_mes[:12]
        ],
    }
    return {
        "ordenes": ordenes_mes[:12],
        "pedidos_activos": len(ordenes_mes_activas),
        "ordenes_mes": len(ordenes_mes),
        "vendido_mes": vendido_mes,
        "cobrado_mes": pagos_mes,
        "egresos_mes": egresos_mes,
        "saldo_inicial_caja": saldo_inicial_caja,
        "movimiento_caja": movimiento_caja_mes,
        "saldo_caja": saldo_final_caja,
        "pendiente_cobrar": pendientes,
        "inversion_productos": inversion_productos,
        "inversion_total": inversion_total,
        "ganancia_estimada": ganancia_estimada,
        "ganancia_real": ganancia_real,
        "fletes_asignados": fletes_asignados,
        "utilidad_neta": utilidad_neta,
        "rentabilidad_neta": rentabilidad_neta,
        "vendido_anio": vendido_anio,
        "inversion_anio": inversion_total_anio,
        "ganancia_real_anio": ganancia_real_anio,
        "fletes_anio": fletes_asignados_anio,
        "utilidad_neta_anio": utilidad_neta_anio,
        "rentabilidad_neta_anio": rentabilidad_neta_anio,
        "dashboard_payload": dashboard_payload,
    }
