# Generated for the user load-adjustment module.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def copiar_cantidades_actuales(apps, schema_editor):
    DetallePlanCarga = apps.get_model(
        'proyectos',
        'DetallePlanCarga'
    )

    for detalle in DetallePlanCarga.objects.all():
        detalle.cantidad_actual = detalle.cantidad
        detalle.peso_actual_kg = (
            detalle.peso_subtotal_kg or Decimal('0.00')
        )
        detalle.save(
            update_fields=[
                'cantidad_actual',
                'peso_actual_kg'
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0029_productocarga_vehiculo_capacidad_carga_kg_plancarga_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plancarga',
            name='estado',
            field=models.CharField(
                choices=[
                    ('BORRADOR', 'BORRADOR'),
                    ('LISTO', 'LISTO'),
                    ('EN_RUTA', 'EN RUTA'),
                    ('COMPLETADO', 'COMPLETADO'),
                    ('CANCELADO', 'CANCELADO'),
                ],
                default='BORRADOR',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='plancarga',
            name='ajustado_por_usuario',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='plancarga',
            name='fecha_revision_usuario',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plancarga',
            name='fecha_ultimo_ajuste_usuario',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='plancarga',
            name='revisado_por_usuario',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='detalleplancarga',
            name='agregado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='productos_carga_agregados',
                to='proyectos.usuario'
            ),
        ),
        migrations.AddField(
            model_name='detalleplancarga',
            name='cantidad_actual',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='detalleplancarga',
            name='fecha_agregado',
            field=models.DateTimeField(default=timezone.now),
        ),
        migrations.AddField(
            model_name='detalleplancarga',
            name='origen',
            field=models.CharField(
                choices=[
                    ('ADMINISTRADOR', 'ADMINISTRADOR'),
                    ('USUARIO', 'USUARIO')
                ],
                default='ADMINISTRADOR',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='detalleplancarga',
            name='peso_actual_kg',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=11
            ),
        ),
        migrations.CreateModel(
            name='AjusteCargaUsuario',
            fields=[
                ('id_ajuste_carga', models.AutoField(primary_key=True, serialize=False)),
                ('tipo_ajuste', models.CharField(choices=[('AGREGAR', 'PRODUCTO AGREGADO'), ('AJUSTAR', 'CANTIDAD AJUSTADA'), ('DESCARTAR', 'PRODUCTO DESCARTADO'), ('RESTAURAR', 'PRODUCTO RESTAURADO')], max_length=20)),
                ('producto_nombre', models.CharField(max_length=200)),
                ('cantidad_anterior', models.PositiveIntegerField(default=0)),
                ('cantidad_nueva', models.PositiveIntegerField(default=0)),
                ('peso_anterior_kg', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=11)),
                ('peso_nuevo_kg', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=11)),
                ('motivo', models.CharField(max_length=250)),
                ('fecha_ajuste', models.DateTimeField(auto_now_add=True)),
                ('detalle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ajustes_usuario', to='proyectos.detalleplancarga')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ajustes_usuario', to='proyectos.plancarga')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ajustes_carga_realizados', to='proyectos.usuario')),
            ],
            options={
                'ordering': ['-fecha_ajuste'],
            },
        ),
        migrations.RunPython(
            copiar_cantidades_actuales,
            migrations.RunPython.noop
        ),
    ]
