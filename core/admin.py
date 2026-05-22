from django.contrib import admin

from .models import Cliente, ItemPedido, MovimientoCaja, Orden, Pago, PrecioReferencia


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "creado")
    search_fields = ("nombre", "telefono")


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "estado", "fecha", "total_final", "total_pagado", "saldo_pendiente")
    list_filter = ("estado", "fecha")
    search_fields = ("cliente__nombre", "items__sku", "items__descripcion")
    inlines = [ItemPedidoInline, PagoInline]


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "orden", "tienda", "sku", "precio_final", "costo_estimado", "costo_real", "proveedor_version")
    search_fields = ("descripcion", "sku", "orden__cliente__nombre")
    list_filter = ("tienda", "proveedor_version")


admin.site.register(PrecioReferencia)
admin.site.register(Pago)
admin.site.register(MovimientoCaja)
