from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import ClienteForm, ItemFormSet, ItemPedidoForm, MovimientoCajaForm, OrdenForm, PagoForm
from .models import Cliente, ItemPedido, MovimientoCaja, Orden, Pago


def money(value):
    return value or Decimal("0.00")


@login_required
def dashboard(request):
    today = timezone.localdate()
    first_day = today.replace(day=1)
    last_day = today.replace(day=monthrange(today.year, today.month)[1])
    pagos_mes = Pago.objects.filter(fecha__range=(first_day, last_day)).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    egresos_mes = MovimientoCaja.objects.filter(
        tipo=MovimientoCaja.Tipo.EGRESO,
        fecha__range=(first_day, last_day),
    ).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    movimientos = MovimientoCaja.objects.all()
    ingresos = movimientos.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    egresos = movimientos.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    ordenes = list(Orden.objects.select_related("cliente").prefetch_related("items", "pagos")[:12])
    pendientes = sum((orden.saldo_pendiente for orden in Orden.objects.prefetch_related("items", "pagos")), Decimal("0.00"))
    ganancia_estimada = sum((orden.ganancia_estimada for orden in Orden.objects.prefetch_related("items")), Decimal("0.00"))
    ganancia_real = sum((orden.ganancia_real for orden in Orden.objects.prefetch_related("items")), Decimal("0.00"))
    return render(request, "core/dashboard.html", {
        "ordenes": ordenes,
        "pedidos_activos": Orden.objects.exclude(estado__in=[Orden.Estado.ENTREGADA, Orden.Estado.CANCELADA]).count(),
        "cobrado_mes": pagos_mes,
        "egresos_mes": egresos_mes,
        "saldo_caja": ingresos - egresos,
        "pendiente_cobrar": pendientes,
        "ganancia_estimada": ganancia_estimada,
        "ganancia_real": ganancia_real,
    })


@login_required
def clientes(request):
    q = request.GET.get("q", "").strip()
    clientes_qs = Cliente.objects.all()
    if q:
        clientes_qs = clientes_qs.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q))
    return render(request, "core/clientes.html", {"clientes": clientes_qs, "q": q})


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
    cliente = get_object_or_404(Cliente, pk=pk)
    return render(request, "core/cliente_detalle.html", {"cliente": cliente})


@login_required
def ordenes(request):
    q = request.GET.get("q", "").strip()
    ordenes_qs = Orden.objects.select_related("cliente").prefetch_related("items", "pagos")
    if q:
        ordenes_qs = ordenes_qs.filter(
            Q(cliente__nombre__icontains=q)
            | Q(items__sku__icontains=q)
            | Q(items__descripcion__icontains=q)
        ).distinct()
    return render(request, "core/ordenes.html", {"ordenes": ordenes_qs, "q": q})


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
def orden_detalle(request, pk):
    orden = get_object_or_404(Orden.objects.select_related("cliente").prefetch_related("items", "pagos"), pk=pk)
    pago_form = PagoForm(initial={"fecha": date.today()})
    item_form = ItemPedidoForm()
    return render(request, "core/orden_detalle.html", {
        "orden": orden,
        "pago_form": pago_form,
        "item_form": item_form,
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
def pago_agregar(request, pk):
    orden = get_object_or_404(Orden, pk=pk)
    form = PagoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pago = form.save(commit=False)
        pago.orden = orden
        pago.save()
        MovimientoCaja.objects.create(
            fecha=pago.fecha,
            tipo=MovimientoCaja.Tipo.INGRESO,
            categoria=MovimientoCaja.Categoria.COBRO_CLIENTE,
            descripcion=f"Cobro a {orden.cliente.nombre} - Orden #{orden.pk}",
            monto=pago.monto,
            pago=pago,
        )
        messages.success(request, "Pago registrado y agregado a caja.")
    return redirect(orden)


@login_required
def caja(request):
    form = MovimientoCajaForm(request.POST or None, initial={"fecha": date.today()})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Movimiento de caja guardado.")
        return redirect("caja")
    movimientos = MovimientoCaja.objects.all()[:80]
    ingresos = MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    egresos = MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    return render(request, "core/caja.html", {
        "form": form,
        "movimientos": movimientos,
        "ingresos": ingresos,
        "egresos": egresos,
        "saldo": ingresos - egresos,
    })


@login_required
def reporte_cliente_pdf(request, pk):
    orden = get_object_or_404(Orden.objects.select_related("cliente").prefetch_related("items", "pagos"), pk=pk)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Reporte de pedido #{orden.pk}", styles["Title"]),
        Paragraph(f"Cliente: {orden.cliente.nombre}", styles["Normal"]),
        Paragraph(f"Fecha: {orden.fecha.strftime('%d/%m/%Y')}", styles["Normal"]),
        Spacer(1, 16),
    ]
    rows = [["Producto", "Descripcion", "Precio"]]
    for item in orden.items.all():
        product_cell = "Sin imagen"
        if item.imagen:
            try:
                product_cell = Image(item.imagen.path, width=64, height=64)
            except Exception:
                product_cell = "Imagen cargada"
        rows.append([product_cell, Paragraph(item.descripcion, styles["BodyText"]), f"${item.precio_final:.2f}"])
    table = Table(rows, colWidths=[90, 330, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.extend([table, Spacer(1, 18)])
    summary = [
        ["Total", f"${orden.total_final:.2f}"],
        ["Inicial sugerida", f"${orden.inicial_sugerida:.2f}"],
        ["Pagado", f"${orden.total_pagado:.2f}"],
        ["Saldo pendiente", f"${orden.saldo_pendiente:.2f}"],
    ]
    summary_table = Table(summary, colWidths=[360, 150])
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(summary_table)
    doc.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"reporte-orden-{orden.pk}.pdf")

# Create your views here.
