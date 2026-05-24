from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_cliente_report_pdf(orden):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=32,
        leftMargin=32,
        topMargin=32,
        bottomMargin=32,
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BrandTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#101828"),
        fontSize=20,
        leading=24,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="Muted",
        parent=styles["Normal"],
        textColor=colors.HexColor("#667085"),
        fontSize=9,
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name="TableText",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
    ))

    header = Table([
        [
            Paragraph("Estefy Fashion", styles["BrandTitle"]),
            Paragraph(f"Pedido #{orden.pk}", styles["BrandTitle"]),
        ],
        [
            Paragraph(f"Cliente: {orden.cliente.nombre}", styles["Normal"]),
            Paragraph(f"Estado: {orden.get_estado_display()}", styles["Normal"]),
        ],
        [
            Paragraph(f"Fecha: {orden.fecha.strftime('%d/%m/%Y')}", styles["Muted"]),
            Paragraph("Reporte para el cliente", styles["Muted"]),
        ],
    ], colWidths=[255, 255])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d9dee8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story = [
        header,
        Spacer(1, 16),
    ]

    rows = [["Imagen", "Producto", "Precio"]]
    for item in orden.items.all():
        product_cell = "Sin imagen"
        if item.imagen:
            try:
                product_cell = Image(item.imagen.path, width=58, height=58)
            except Exception:
                product_cell = "Imagen cargada"
        elif item.imagen_url:
            product_cell = "Imagen referencial"
        description = item.descripcion
        if item.sku:
            description = f"{description}<br/><font color='#667085'>SKU: {item.sku}</font>"
        rows.append([
            product_cell,
            Paragraph(description, styles["TableText"]),
            f"USD {item.precio_final:.2f}",
        ])

    table = Table(rows, colWidths=[80, 330, 100], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4f4f3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#101828")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9dee8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([table, Spacer(1, 18)])

    summary = [
        ["Total", f"USD {orden.total_final:.2f}"],
        ["Inicial sugerida", f"USD {orden.inicial_sugerida:.2f}"],
        ["Pagado", f"USD {orden.total_pagado:.2f}"],
        ["Saldo pendiente", f"USD {orden.saldo_pendiente:.2f}"],
    ]
    summary_table = Table(summary, colWidths=[360, 150], hAlign="RIGHT")
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9dee8")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([summary_table])
    doc.build(story)
    buffer.seek(0)
    return buffer
