from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clientes/", views.clientes, name="clientes"),
    path("clientes/nuevo/", views.cliente_crear, name="cliente_crear"),
    path("clientes/<int:pk>/", views.cliente_detalle, name="cliente_detalle"),
    path("ordenes/", views.ordenes, name="ordenes"),
    path("ordenes/nueva/", views.orden_crear, name="orden_crear"),
    path("ordenes/extraer-imagen/", views.extraer_imagen_producto, name="extraer_imagen_producto"),
    path("ordenes/<int:pk>/", views.orden_detalle, name="orden_detalle"),
    path("ordenes/<int:pk>/editar/", views.orden_editar, name="orden_editar"),
    path("ordenes/<int:pk>/items/agregar/", views.item_agregar, name="item_agregar"),
    path("ordenes/<int:pk>/pagos/agregar/", views.pago_agregar, name="pago_agregar"),
    path("ordenes/<int:pk>/reporte.pdf", views.reporte_cliente_pdf, name="reporte_cliente_pdf"),
    path("caja/", views.caja, name="caja"),
]
