import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ClienteForm, EnvioForm, ItemFormSet, ItemPedidoForm, MovimientoCajaForm, OrdenForm, PagoForm
from .models import Cliente, Envio, ItemPedido, MovimientoCaja, Orden, OrdenEnvio, Pago
from .payloads import (
    cliente_detalle_payload,
    cliente_payload,
    dashboard_context,
    envio_payload,
    movimiento_payload,
    orden_detalle_payload,
    orden_envio_form_payload,
    orden_payload,
)
from .reports import build_cliente_report_pdf
from .services.caja import sincronizar_envio_caja, sincronizar_pago_caja, total_movimientos
from .services.envios import recalcular_flete_envio, repartir_flete, sincronizar_estado_ordenes_envio
from .services.scraping import find_product_image_url, is_safe_public_url
from .utils import decimal_payload, parse_date_param


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html", dashboard_context(request))


@login_required
def clientes(request):
    q = request.GET.get("q", "").strip()
    clientes_qs = Cliente.objects.prefetch_related("ordenes__items", "ordenes__pagos")
    if q:
        clientes_qs = clientes_qs.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q))
    clientes_list = list(clientes_qs)
    clientes_payload = {
        "q": q,
        "urls": {
            "nuevoCliente": reverse("cliente_crear"),
        },
        "clientes": [cliente_payload(cliente) for cliente in clientes_list],
    }
    return render(request, "core/clientes.html", {
        "clientes": clientes_list,
        "q": q,
        "clientes_payload": clientes_payload,
    })


@login_required
def cliente_crear(request):
    form = ClienteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente guardado.")
        return redirect(cliente)
    return render(request, "core/form.html", {"form": form, "title": "Nuevo cliente", "button": "Guardar cliente"})


@login_required
def cliente_detalle(request, pk):
    cliente = get_object_or_404(Cliente.objects.prefetch_related("ordenes__items", "ordenes__pagos"), pk=pk)
    return render(request, "core/cliente_detalle.html", {
        "cliente": cliente,
        "cliente_detalle_payload": cliente_detalle_payload(cliente),
    })


@login_required
def ordenes(request):
    q = request.GET.get("q", "").strip()
    fecha_desde = parse_date_param(request.GET.get("desde"))
    fecha_hasta = parse_date_param(request.GET.get("hasta"))
    ordenes_qs = Orden.objects.select_related("cliente").prefetch_related("items", "pagos")
    if fecha_desde:
        ordenes_qs = ordenes_qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        ordenes_qs = ordenes_qs.filter(fecha__lte=fecha_hasta)
    if q:
        ordenes_qs = ordenes_qs.filter(
            Q(cliente__nombre__icontains=q)
            | Q(items__sku__icontains=q)
            | Q(items__descripcion__icontains=q)
        ).distinct()
    ordenes_list = list(ordenes_qs)
    ordenes_payload = {
        "q": q,
        "fechaDesde": fecha_desde.isoformat() if fecha_desde else "",
        "fechaHasta": fecha_hasta.isoformat() if fecha_hasta else "",
        "urls": {
            "nuevaOrden": reverse("orden_crear"),
        },
        "estados": [
            {"value": value, "label": label}
            for value, label in Orden.Estado.choices
        ],
        "ordenes": [orden_payload(orden) for orden in ordenes_list],
    }
    return render(request, "core/ordenes.html", {
        "ordenes": ordenes_list,
        "q": q,
        "ordenes_payload": ordenes_payload,
    })


@login_required
def orden_crear(request):
    form = OrdenForm(request.POST or None)
    formset = ItemFormSet(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        orden = form.save()
        formset.instance = orden
        formset.save()
        if orden.inicial_sugerida == Decimal("0.00"):
            orden.inicial_sugerida = (orden.total_final * Decimal("0.50")).quantize(Decimal("0.01"))
            orden.save(update_fields=["inicial_sugerida"])
        messages.success(request, "Orden creada.")
        return redirect(orden)
    return render(request, "core/orden_form.html", {"form": form, "formset": formset, "title": "Nueva orden"})


@login_required
def extraer_imagen_producto(request):
    product_url = request.GET.get("url", "").strip()
    if not product_url:
        return JsonResponse({"ok": False, "error": "Coloca primero el link del producto."}, status=400)
    if not is_safe_public_url(product_url):
        return JsonResponse({"ok": False, "error": "El link no es una URL publica valida."}, status=400)
    try:
        image_url = find_product_image_url(product_url)
    except Exception:
        return JsonResponse({"ok": False, "error": "No se pudo leer la pagina del producto."}, status=502)
    if not image_url:
        return JsonResponse({"ok": False, "error": "No encontre una imagen principal en ese link."}, status=404)
    return JsonResponse({"ok": True, "image_url": image_url})


@login_required
def orden_detalle(request, pk):
    orden = get_object_or_404(
        Orden.objects.select_related("cliente", "envio_asignado__envio").prefetch_related("items", "pagos"),
        pk=pk,
    )
    pago_form = PagoForm(initial={"fecha": date.today()})
    item_form = ItemPedidoForm()
    return render(request, "core/orden_detalle.html", {
        "orden": orden,
        "pago_form": pago_form,
        "item_form": item_form,
        "orden_detalle_payload": orden_detalle_payload(orden, get_token(request)),
    })


@login_required
def orden_cambiar_estado(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metodo no permitido."}, status=405)
    orden = get_object_or_404(Orden, pk=pk)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Solicitud invalida."}, status=400)
    nuevo_estado = payload.get("estado")
    estados_validos = {value for value, _label in Orden.Estado.choices}
    if nuevo_estado not in estados_validos:
        return JsonResponse({"ok": False, "error": "Estado invalido."}, status=400)
    orden.estado = nuevo_estado
    orden.save(update_fields=["estado", "actualizado"])
    return JsonResponse({
        "ok": True,
        "estado": orden.estado,
        "estadoDisplay": orden.get_estado_display(),
    })


@login_required
def orden_editar(request, pk):
    orden = get_object_or_404(Orden, pk=pk)
    form = OrdenForm(request.POST or None, instance=orden)
    formset = ItemFormSet(request.POST or None, request.FILES or None, instance=orden)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, "Orden actualizada.")
        return redirect(orden)
    return render(request, "core/orden_form.html", {"form": form, "formset": formset, "title": f"Editar orden #{orden.pk}"})


@login_required
def item_agregar(request, pk):
    orden = get_object_or_404(Orden, pk=pk)
    form = ItemPedidoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.orden = orden
        item.save()
        messages.success(request, "Producto agregado.")
    return redirect(orden)


@login_required
def item_editar(request, pk):
    item = get_object_or_404(ItemPedido.objects.select_related("orden"), pk=pk)
    form = ItemPedidoForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Producto actualizado.")
        return redirect(item.orden)
    return render(request, "core/form.html", {
        "form": form,
        "title": f"Editar producto - Orden #{item.orden_id}",
        "button": "Guardar producto",
    })


@login_required
def item_eliminar(request, pk):
    if request.method != "POST":
        return redirect("ordenes")
    item = get_object_or_404(ItemPedido.objects.select_related("orden"), pk=pk)
    orden = item.orden
    item.delete()
    messages.success(request, "Producto eliminado.")
    return redirect(orden)


@login_required
def pago_agregar(request, pk):
    orden = get_object_or_404(Orden, pk=pk)
    form = PagoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pago = form.save(commit=False)
        pago.orden = orden
        pago.save()
        sincronizar_pago_caja(pago)
        messages.success(request, "Pago registrado y agregado a caja.")
    return redirect(orden)


@login_required
def pago_editar(request, pk):
    pago = get_object_or_404(Pago.objects.select_related("orden__cliente"), pk=pk)
    form = PagoForm(request.POST or None, instance=pago)
    if request.method == "POST" and form.is_valid():
        pago = form.save()
        sincronizar_pago_caja(pago)
        messages.success(request, "Pago actualizado y caja sincronizada.")
        return redirect(pago.orden)
    return render(request, "core/form.html", {
        "form": form,
        "title": f"Editar pago - Orden #{pago.orden_id}",
        "button": "Guardar pago",
    })


@login_required
def pago_eliminar(request, pk):
    if request.method != "POST":
        return redirect("ordenes")
    pago = get_object_or_404(Pago.objects.select_related("orden"), pk=pk)
    orden = pago.orden
    try:
        pago.movimiento_caja.delete()
    except MovimientoCaja.DoesNotExist:
        pass
    pago.delete()
    messages.success(request, "Pago eliminado y caja sincronizada.")
    return redirect(orden)


@login_required
def caja(request):
    fecha_desde = parse_date_param(request.GET.get("desde"))
    fecha_hasta = parse_date_param(request.GET.get("hasta"))
    form = MovimientoCajaForm(request.POST or None, initial={"fecha": date.today()})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Movimiento de caja guardado.")
        return redirect("caja")
    movimientos_qs = MovimientoCaja.objects.all()
    movimientos_filtrados_qs = movimientos_qs
    if fecha_desde:
        movimientos_filtrados_qs = movimientos_filtrados_qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        movimientos_filtrados_qs = movimientos_filtrados_qs.filter(fecha__lte=fecha_hasta)
    movimientos = list(movimientos_qs)
    ingresos, egresos, saldo_total = total_movimientos(movimientos_qs)
    ingresos_filtrados, egresos_filtrados, movimiento_periodo = total_movimientos(movimientos_filtrados_qs)
    if fecha_desde:
        _ingresos_anteriores, _egresos_anteriores, saldo_inicial = total_movimientos(movimientos_qs.filter(fecha__lt=fecha_desde))
    else:
        saldo_inicial = Decimal("0.00")
    saldo_final = saldo_inicial + movimiento_periodo
    caja_payload = {
        "ingresos": decimal_payload(ingresos),
        "egresos": decimal_payload(egresos),
        "saldo": decimal_payload(saldo_total),
        "ingresosFiltrados": decimal_payload(ingresos_filtrados),
        "egresosFiltrados": decimal_payload(egresos_filtrados),
        "saldoInicial": decimal_payload(saldo_inicial),
        "movimientoPeriodo": decimal_payload(movimiento_periodo),
        "saldoFinal": decimal_payload(saldo_final),
        "fechaDesde": fecha_desde.isoformat() if fecha_desde else "",
        "fechaHasta": fecha_hasta.isoformat() if fecha_hasta else "",
        "csrfToken": get_token(request),
        "movimientos": [movimiento_payload(movimiento) for movimiento in movimientos],
        "tipos": [
            {"value": value, "label": label}
            for value, label in MovimientoCaja.Tipo.choices
        ],
    }
    return render(request, "core/caja.html", {
        "form": form,
        "movimientos": movimientos,
        "ingresos": ingresos,
        "egresos": egresos,
        "saldo": saldo_total,
        "ingresos_filtrados": ingresos_filtrados,
        "egresos_filtrados": egresos_filtrados,
        "saldo_inicial": saldo_inicial,
        "movimiento_periodo": movimiento_periodo,
        "saldo_final": saldo_final,
        "caja_payload": caja_payload,
    })


@login_required
def movimiento_editar(request, pk):
    movimiento = get_object_or_404(MovimientoCaja, pk=pk)
    if movimiento.pago_id is not None:
        messages.error(request, "Los movimientos de pagos se editan desde la orden.")
        return redirect("caja")
    if hasattr(movimiento, "envio"):
        messages.error(request, "Los fletes de envios se editan desde el envio.")
        return redirect("caja")
    form = MovimientoCajaForm(request.POST or None, instance=movimiento)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Movimiento de caja actualizado.")
        return redirect("caja")
    return render(request, "core/form.html", {
        "form": form,
        "title": "Editar movimiento de caja",
        "button": "Guardar movimiento",
    })


@login_required
def movimiento_eliminar(request, pk):
    if request.method != "POST":
        return redirect("caja")
    movimiento = get_object_or_404(MovimientoCaja, pk=pk)
    if movimiento.pago_id is not None:
        messages.error(request, "Los movimientos de pagos se eliminan desde la orden.")
        return redirect("caja")
    if hasattr(movimiento, "envio"):
        messages.error(request, "Los fletes de envios se eliminan desde el envio.")
        return redirect("caja")
    movimiento.delete()
    messages.success(request, "Movimiento de caja eliminado.")
    return redirect("caja")


@login_required
def envios(request):
    envios_list = list(
        Envio.objects.prefetch_related("ordenes_envio__orden__cliente", "ordenes_envio__orden__items", "ordenes_envio__orden__pagos")
    )
    ordenes_disponibles = list(
        Orden.objects.filter(estado=Orden.Estado.COMPRADA)
        .select_related("cliente")
        .prefetch_related("items", "pagos")
    )
    payload = {
        "urls": {
            "nuevoEnvio": reverse("envio_crear"),
        },
        "envios": [envio_payload(envio) for envio in envios_list],
        "ordenesDisponibles": [orden_payload(orden) for orden in ordenes_disponibles],
    }
    return render(request, "core/envios.html", {
        "envios_payload": payload,
    })


@login_required
def envio_crear(request):
    ordenes_disponibles = list(
        Orden.objects.filter(estado=Orden.Estado.COMPRADA)
        .select_related("cliente")
        .prefetch_related("items", "pagos")
    )
    today = date.today()
    form = EnvioForm(request.POST or None, initial={
        "estado": Envio.Estado.EN_TRANSITO,
        "fecha_salida": today,
        "fecha_pago_flete": today,
        "periodo_utilidad": today.replace(day=1),
    })
    if request.method == "POST" and form.is_valid():
        orden_ids = request.POST.getlist("ordenes")
        ordenes_seleccionadas = [
            orden for orden in ordenes_disponibles
            if str(orden.id) in orden_ids
        ]
        if not ordenes_seleccionadas:
            messages.error(request, "Selecciona al menos una orden comprada para crear el envio.")
        else:
            with transaction.atomic():
                envio = form.save()
                asignaciones = repartir_flete(ordenes_seleccionadas, envio.costo_flete)
                for orden in ordenes_seleccionadas:
                    OrdenEnvio.objects.create(
                        envio=envio,
                        orden=orden,
                        costo_flete_asignado=asignaciones[orden.id],
                    )
                    orden.estado = Orden.Estado.EN_TRANSITO
                    orden.save(update_fields=["estado", "actualizado"])
                sincronizar_envio_caja(envio)
            messages.success(request, "Envio creado, flete repartido y ordenes marcadas en transito.")
            return redirect(envio)
    return render(request, "core/envio_form.html", {
        "form": form,
        "ordenes": [orden_envio_form_payload(orden) for orden in ordenes_disponibles],
    })


@login_required
def envio_detalle(request, pk):
    envio = get_object_or_404(
        Envio.objects.prefetch_related("ordenes_envio__orden__cliente", "ordenes_envio__orden__items", "ordenes_envio__orden__pagos"),
        pk=pk,
    )
    return render(request, "core/envio_detalle.html", {
        "envio": envio,
        "envio_payload": envio_payload(envio),
    })


@login_required
def envio_editar(request, pk):
    envio = get_object_or_404(Envio.objects.prefetch_related("ordenes_envio__orden__items"), pk=pk)
    form = EnvioForm(request.POST or None, instance=envio)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            envio = form.save()
            recalcular_flete_envio(envio)
            sincronizar_envio_caja(envio)
            ordenes_actualizadas = sincronizar_estado_ordenes_envio(envio)
        messages.success(request, f"Envio actualizado. Ordenes sincronizadas: {ordenes_actualizadas}.")
        return redirect(envio)
    return render(request, "core/form.html", {
        "form": form,
        "title": f"Editar envio - {envio.nombre}",
        "button": "Guardar envio",
    })


@login_required
def envio_cambiar_estado(request, pk):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metodo no permitido."}, status=405)
    envio = get_object_or_404(
        Envio.objects.prefetch_related("ordenes_envio__orden__cliente", "ordenes_envio__orden__items", "ordenes_envio__orden__pagos"),
        pk=pk,
    )
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Solicitud invalida."}, status=400)
    nuevo_estado = payload.get("estado")
    estados_validos = {value for value, _label in Envio.Estado.choices}
    if nuevo_estado not in estados_validos:
        return JsonResponse({"ok": False, "error": "Estado invalido."}, status=400)
    with transaction.atomic():
        envio.estado = nuevo_estado
        update_fields = ["estado"]
        if nuevo_estado == Envio.Estado.EN_TRANSITO and envio.fecha_salida is None:
            envio.fecha_salida = timezone.localdate()
            update_fields.append("fecha_salida")
        if nuevo_estado == Envio.Estado.RECIBIDO and envio.fecha_llegada is None:
            envio.fecha_llegada = timezone.localdate()
            update_fields.append("fecha_llegada")
        envio.save(update_fields=update_fields)
        ordenes_actualizadas = sincronizar_estado_ordenes_envio(envio)
    envio.refresh_from_db()
    envio = Envio.objects.prefetch_related("ordenes_envio__orden__cliente", "ordenes_envio__orden__items", "ordenes_envio__orden__pagos").get(pk=envio.pk)
    return JsonResponse({
        "ok": True,
        "estado": envio.estado,
        "estadoDisplay": envio.get_estado_display(),
        "fechaSalidaDisplay": envio.fecha_salida.strftime("%d/%m/%Y") if envio.fecha_salida else "-",
        "fechaLlegadaDisplay": envio.fecha_llegada.strftime("%d/%m/%Y") if envio.fecha_llegada else "-",
        "ordenesActualizadas": ordenes_actualizadas,
        "ordenes": [orden_payload(relacion.orden) for relacion in envio.ordenes_envio.all()],
    })


@login_required
def reporte_cliente_pdf(request, pk):
    orden = get_object_or_404(Orden.objects.select_related("cliente").prefetch_related("items", "pagos"), pk=pk)
    buffer = build_cliente_report_pdf(orden)
    return FileResponse(buffer, as_attachment=True, filename=f"reporte-orden-{orden.pk}.pdf")
