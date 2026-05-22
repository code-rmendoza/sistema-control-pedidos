from django import forms
from django.forms import inlineformset_factory

from .models import Cliente, ItemPedido, MovimientoCaja, Orden, Pago, PrecioReferencia


class DateInput(forms.DateInput):
    input_type = "date"


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "telefono", "notas"]
        labels = {"nombre": "Nombre", "telefono": "Telefono", "notas": "Notas"}


class OrdenForm(forms.ModelForm):
    class Meta:
        model = Orden
        fields = ["cliente", "estado", "inicial_sugerida", "notas"]
        labels = {
            "cliente": "Cliente",
            "estado": "Estado",
            "inicial_sugerida": "Inicial sugerida",
            "notas": "Notas internas",
        }


class ItemPedidoForm(forms.ModelForm):
    class Meta:
        model = ItemPedido
        fields = [
            "imagen",
            "imagen_url",
            "link",
            "tienda",
            "sku",
            "descripcion",
            "precio_final",
            "costo_estimado",
            "costo_real",
            "precio_shein_eeuu",
            "precio_shein_espana",
            "precio_shein_venezuela",
            "precio_shein_colombia",
            "proveedor_version",
        ]
        labels = {
            "imagen": "Imagen",
            "imagen_url": "URL de imagen",
            "link": "Link del producto",
            "tienda": "Tienda",
            "sku": "SKU",
            "descripcion": "Descripcion",
            "precio_final": "Precio final al cliente",
            "costo_estimado": "Costo estimado",
            "costo_real": "Costo real",
            "precio_shein_eeuu": "Shein EEUU",
            "precio_shein_espana": "Shein Espana",
            "precio_shein_venezuela": "Shein Venezuela",
            "precio_shein_colombia": "Shein Colombia",
            "proveedor_version": "Version usada",
        }


class PrecioReferenciaForm(forms.ModelForm):
    class Meta:
        model = PrecioReferencia
        fields = ["shein_eeuu", "shein_espana", "shein_venezuela", "shein_colombia"]


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ["fecha", "monto", "metodo", "nota"]
        widgets = {"fecha": DateInput()}
        labels = {"fecha": "Fecha", "monto": "Monto", "metodo": "Metodo", "nota": "Nota"}


class MovimientoCajaForm(forms.ModelForm):
    class Meta:
        model = MovimientoCaja
        fields = ["fecha", "tipo", "categoria", "descripcion", "monto"]
        widgets = {"fecha": DateInput()}
        labels = {
            "fecha": "Fecha",
            "tipo": "Tipo",
            "categoria": "Categoria",
            "descripcion": "Descripcion",
            "monto": "Monto",
        }


ItemFormSet = inlineformset_factory(
    Orden,
    ItemPedido,
    form=ItemPedidoForm,
    extra=1,
    can_delete=True,
)
