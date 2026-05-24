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
    path("ordenes/<int:pk>/estado/", views.orden_cambiar_estado, name="orden_cambiar_estado"),
    path("ordenes/<int:pk>/editar/", views.orden_editar, name="orden_editar"),
    path("ordenes/<int:pk>/items/agregar/", views.item_agregar, name="item_agregar"),
    path("ordenes/<int:pk>/pagos/agregar/", views.pago_agregar, name="pago_agregar"),
    path("ordenes/<int:pk>/reporte.pdf", views.reporte_cliente_pdf, name="reporte_cliente_pdf"),
    path("envios/", views.envios, name="envios"),
    path("envios/nuevo/", views.envio_crear, name="envio_crear"),
    path("envios/<int:pk>/", views.envio_detalle, name="envio_detalle"),
    path("envios/<int:pk>/editar/", views.envio_editar, name="envio_editar"),
    path("envios/<int:pk>/estado/", views.envio_cambiar_estado, name="envio_cambiar_estado"),
    path("pagos/<int:pk>/editar/", views.pago_editar, name="pago_editar"),
    path("pagos/<int:pk>/eliminar/", views.pago_eliminar, name="pago_eliminar"),
    path("items/<int:pk>/editar/", views.item_editar, name="item_editar"),
    path("items/<int:pk>/eliminar/", views.item_eliminar, name="item_eliminar"),
    path("caja/", views.caja, name="caja"),
    path("caja/<int:pk>/editar/", views.movimiento_editar, name="movimiento_editar"),
    path("caja/<int:pk>/eliminar/", views.movimiento_eliminar, name="movimiento_eliminar"),
]
