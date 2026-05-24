from django import forms
from django.forms import inlineformset_factory

from .models import Cliente, Envio, ItemPedido, MovimientoCaja, Orden, Pago


class DateInput(forms.DateInput):
    input_type = "date"


class MonthInput(forms.DateInput):
    input_type = "month"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m")


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "telefono", "notas"]
        labels = {"nombre": "Nombre", "telefono": "Telefono", "notas": "Notas"}


class OrdenForm(forms.ModelForm):
    class Meta:
        model = Orden
        fields = ["cliente", "fecha", "estado", "inicial_sugerida", "notas"]
        widgets = {"fecha": DateInput()}
        labels = {
            "cliente": "Cliente",
            "fecha": "Fecha de orden",
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


class EnvioForm(forms.ModelForm):
    periodo_utilidad = forms.DateField(
        input_formats=["%Y-%m", "%Y-%m-%d"],
        widget=MonthInput(),
        label="Mes contable de utilidad",
    )

    class Meta:
        model = Envio
        fields = [
            "nombre",
            "estado",
            "courier",
            "fecha_salida",
            "fecha_llegada",
            "fecha_pago_flete",
            "periodo_utilidad",
            "costo_flete",
            "notas",
        ]
        widgets = {
            "fecha_salida": DateInput(),
            "fecha_llegada": DateInput(),
            "fecha_pago_flete": DateInput(),
        }
        labels = {
            "nombre": "Nombre",
            "estado": "Estado",
            "courier": "Courier",
            "fecha_salida": "Fecha de salida",
            "fecha_llegada": "Fecha de llegada",
            "fecha_pago_flete": "Fecha de pago del flete",
            "costo_flete": "Costo de flete",
            "notas": "Notas",
        }

    def clean_periodo_utilidad(self):
        value = self.cleaned_data["periodo_utilidad"]
        return value.replace(day=1)


ItemFormSet = inlineformset_factory(
    Orden,
    ItemPedido,
    form=ItemPedidoForm,
    extra=1,
    can_delete=True,
)
