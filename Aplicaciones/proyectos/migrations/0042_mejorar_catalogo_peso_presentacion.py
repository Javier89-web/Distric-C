from decimal import Decimal

from django.db import migrations, models


def preparar_productos_existentes(apps, schema_editor):
    ProductoCarga = apps.get_model('proyectos', 'ProductoCarga')

    multiplicadores_anteriores = {
        'UNIDAD': 1,
        'BOTELLA': 1,
        'GALON': 1,
        'FUNDA': 6,
        'PAQUETE': 6,
        'CAJA': 12,
        'JABA': 12,
    }

    for producto in ProductoCarga.objects.all().iterator():
        presentacion_anterior = producto.presentacion_producto
        cantidad = multiplicadores_anteriores.get(presentacion_anterior, 1)

        if presentacion_anterior == 'FUNDA':
            producto.presentacion_producto = 'PAQUETE'

        producto.unidades_por_presentacion = cantidad

        # Conserva exactamente el peso que ya utilizaba el sistema. Para los
        # registros antiguos se expresa el contenido individual equivalente en
        # kg; al editar un producto del catálogo, el formulario puede reemplazar
        # esta referencia por su volumen real en ml/L.
        if producto.peso_unitario_kg is not None and cantidad > 0:
            producto.contenido_unitario = (
                Decimal(producto.peso_unitario_kg) / Decimal(cantidad)
            ).quantize(Decimal('0.001'))
            producto.unidad_contenido = 'KG'

        producto.save(
            update_fields=[
                'presentacion_producto',
                'contenido_unitario',
                'unidad_contenido',
                'unidades_por_presentacion',
            ]
        )


def revertir_productos_existentes(apps, schema_editor):
    # No se vuelve a FUNDA porque no existe forma segura de distinguir si un
    # PAQUETE actual provino de una funda o ya era paquete desde el inicio.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0041_historialpreciocombustible_nota'),
    ]

    operations = [
        migrations.AddField(
            model_name='productocarga',
            name='contenido_unitario',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=9,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='productocarga',
            name='unidad_contenido',
            field=models.CharField(
                blank=True,
                choices=[
                    ('ML', 'ml'),
                    ('L', 'L'),
                    ('G', 'g'),
                    ('KG', 'kg'),
                ],
                default='',
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name='productocarga',
            name='unidades_por_presentacion',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(
            preparar_productos_existentes,
            revertir_productos_existentes,
        ),
        migrations.AlterField(
            model_name='productocarga',
            name='presentacion_producto',
            field=models.CharField(
                choices=[
                    ('GALON', 'GALÓN'),
                    ('JABA', 'JABA'),
                    ('PAQUETE', 'PAQUETE'),
                    ('BOTELLA', 'BOTELLA'),
                    ('CAJA', 'CAJA'),
                    ('UNIDAD', 'UNIDAD'),
                ],
                max_length=20,
            ),
        ),
    ]
