import ipaddress
import json
import re
import socket
from calendar import monthrange
from datetime import date
from decimal import Decimal
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.db.models import Q, Sum
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import ClienteForm, ItemFormSet, ItemPedidoForm, MovimientoCajaForm, OrdenForm, PagoForm
from .models import Cliente, ItemPedido, MovimientoCaja, Orden, Pago


class ProductImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self._in_json_ld = False
        self._json_ld_chunks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
            content = attrs.get("content")
            if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src", "image"} and content:
                self.images.append(content)
        if tag == "link":
            rel = (attrs.get("rel") or "").lower()
            href = attrs.get("href")
            if "image_src" in rel and href:
                self.images.append(href)
        if tag in {"img", "source"}:
            for key in ("src", "data-src", "data-original", "data-lazy", "data-image"):
                value = attrs.get(key)
                if value:
                    self.images.append(value)
            srcset = attrs.get("srcset") or attrs.get("data-srcset")
            if srcset:
                self.images.extend(parse_srcset(srcset))
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_chunks = []

    def handle_data(self, data):
        if self._in_json_ld:
            self._json_ld_chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self._extract_json_images("".join(self._json_ld_chunks))

    def _extract_json_images(self, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        self._walk_json(data)

    def _walk_json(self, value):
        if isinstance(value, dict):
            image = value.get("image")
            if isinstance(image, str):
                self.images.append(image)
            elif isinstance(image, list):
                self.images.extend(item for item in image if isinstance(item, str))
            elif isinstance(image, dict) and isinstance(image.get("url"), str):
                self.images.append(image["url"])
            for child in value.values():
                self._walk_json(child)
        elif isinstance(value, list):
            for child in value:
                self._walk_json(child)


def parse_srcset(srcset):
    urls = []
    for candidate in srcset.split(","):
        url = candidate.strip().split(" ")[0]
        if url:
            urls.append(url)
    return urls


def normalize_scraped_url(raw_url):
    url = unescape(raw_url.strip().strip("\"'"))
    url = url.replace("\\/", "/")
    try:
        url = bytes(url, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        pass
    return url


def extract_image_urls_from_text(html):
    patterns = [
        r'https?:\\?/\\?/[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<>\s]*)?',
        r'//[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<>\s]*)?',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, html, flags=re.IGNORECASE))
    return urls


def image_score(image_url):
    parsed = urlparse(image_url)
    value = image_url.lower()
    score = 0
    if parsed.netloc:
        score += 2
    if any(token in value for token in ("product", "goods", "main", "large", "zoom", "images3_pi", "ltwebstatic")):
        score += 6
    if any(token in value for token in ("logo", "sprite", "icon", "avatar", "placeholder", "loading", "banner")):
        score -= 8
    if any(size in value for size in ("405x552", "600x", "800x", "1200x")):
        score += 2
    return score


def money(value):
    return value or Decimal("0.00")


def decimal_payload(value):
    return str(money(value).quantize(Decimal("0.01")))


def is_safe_public_url(raw_url):
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def find_product_image_url(product_url):
    request = Request(
        product_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SistemaImport/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ""
        html = response.read(1_500_000).decode("utf-8", errors="ignore")

    parser = ProductImageParser()
    parser.feed(html)
    candidates = parser.images + extract_image_urls_from_text(html)
    normalized = []
    seen = set()
    for image_url in candidates:
        image_url = normalize_scraped_url(image_url)
        absolute_url = urljoin(product_url, image_url)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        if urlparse(absolute_url).scheme in {"http", "https"}:
            normalized.append(absolute_url)
    normalized.sort(key=image_score, reverse=True)
    if normalized:
        return normalized[0]
    return ""


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
        "pagadoCompleto": orden.pagado_completo,
        "itemsCount": orden.items.count(),
        "url": orden.get_absolute_url(),
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


def movimiento_payload(movimiento):
    editable = movimiento.pago_id is None
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
        "esPago": not editable,
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
    pedidos_activos = Orden.objects.exclude(estado__in=[Orden.Estado.ENTREGADA, Orden.Estado.CANCELADA]).count()
    dashboard_payload = {
        "pedidosActivos": pedidos_activos,
        "cobradoMes": decimal_payload(pagos_mes),
        "egresosMes": decimal_payload(egresos_mes),
        "saldoCaja": decimal_payload(ingresos - egresos),
        "pendienteCobrar": decimal_payload(pendientes),
        "gananciaEstimada": decimal_payload(ganancia_estimada),
        "gananciaReal": decimal_payload(ganancia_real),
        "urls": {
            "nuevaOrden": reverse("orden_crear"),
            "ordenes": reverse("ordenes"),
        },
        "ordenes": [
            orden_payload(orden)
            for orden in ordenes
        ],
    }
    return render(request, "core/dashboard.html", {
        "ordenes": ordenes,
        "pedidos_activos": pedidos_activos,
        "cobrado_mes": pagos_mes,
        "egresos_mes": egresos_mes,
        "saldo_caja": ingresos - egresos,
        "pendiente_cobrar": pendientes,
        "ganancia_estimada": ganancia_estimada,
        "ganancia_real": ganancia_real,
        "dashboard_payload": dashboard_payload,
    })


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
    ordenes_qs = Orden.objects.select_related("cliente").prefetch_related("items", "pagos")
    if q:
        ordenes_qs = ordenes_qs.filter(
            Q(cliente__nombre__icontains=q)
            | Q(items__sku__icontains=q)
            | Q(items__descripcion__icontains=q)
        ).distinct()
    ordenes_list = list(ordenes_qs)
    ordenes_payload = {
        "q": q,
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
    orden = get_object_or_404(Orden.objects.select_related("cliente").prefetch_related("items", "pagos"), pk=pk)
    pago_form = PagoForm(initial={"fecha": date.today()})
    item_form = ItemPedidoForm()
    orden_detalle_payload = {
        **orden_payload(orden),
        "clienteUrl": orden.cliente.get_absolute_url(),
        "csrfToken": get_token(request),
        "inicialSugerida": decimal_payload(orden.inicial_sugerida),
        "gananciaEstimada": decimal_payload(orden.ganancia_estimada),
        "gananciaReal": decimal_payload(orden.ganancia_real),
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
    return render(request, "core/orden_detalle.html", {
        "orden": orden,
        "pago_form": pago_form,
        "item_form": item_form,
        "orden_detalle_payload": orden_detalle_payload,
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
    form = MovimientoCajaForm(request.POST or None, initial={"fecha": date.today()})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Movimiento de caja guardado.")
        return redirect("caja")
    movimientos = MovimientoCaja.objects.all()[:80]
    ingresos = MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.INGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    egresos = MovimientoCaja.objects.filter(tipo=MovimientoCaja.Tipo.EGRESO).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    caja_payload = {
        "ingresos": decimal_payload(ingresos),
        "egresos": decimal_payload(egresos),
        "saldo": decimal_payload(ingresos - egresos),
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
        "saldo": ingresos - egresos,
        "caja_payload": caja_payload,
    })


@login_required
def movimiento_editar(request, pk):
    movimiento = get_object_or_404(MovimientoCaja, pk=pk)
    if movimiento.pago_id is not None:
        messages.error(request, "Los movimientos de pagos se editan desde la orden.")
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
    movimiento.delete()
    messages.success(request, "Movimiento de caja eliminado.")
    return redirect("caja")


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
