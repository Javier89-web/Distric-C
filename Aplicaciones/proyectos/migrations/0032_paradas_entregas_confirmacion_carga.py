from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0031_vehiculo_foto_vehiculo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plancarga',
            name='estado',
            field=models.CharField(
                choices=[
                    ('BORRADOR', 'BORRADOR'),
                    ('LISTO', 'LISTO'),
                    ('CONFIRMADO', 'CONFIRMADO'),
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
            name='confirmado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='planes_carga_confirmados',
                to='proyectos.usuario'
            ),
        ),
        migrations.AddField(
            model_name='plancarga',
            name='fecha_confirmacion',
            field=models.DateTimeField(
                blank=True,
                null=True
            ),
        ),
        migrations.CreateModel(
            name='ParadaPlanCarga',
            fields=[
                (
                    'id_parada_plan_carga',
                    models.AutoField(
                        primary_key=True,
                        serialize=False
                    )
                ),
                (
                    'nombre_parada',
                    models.CharField(max_length=150)
                ),
                (
                    'direccion_parada',
                    models.CharField(max_length=250)
                ),
                (
                    'latitud',
                    models.DecimalField(
                        decimal_places=7,
                        max_digits=10
                    )
                ),
                (
                    'longitud',
                    models.DecimalField(
                        decimal_places=7,
                        max_digits=10
                    )
                ),
                (
                    'orden',
                    models.PositiveIntegerField()
                ),
                (
                    'observaciones',
                    models.CharField(
                        blank=True,
                        max_length=250
                    )
                ),
                (
                    'fecha_creacion',
                    models.DateTimeField(auto_now_add=True)
                ),
                (
                    'plan',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='paradas',
                        to='proyectos.plancarga'
                    )
                ),
            ],
            options={
                'ordering': [
                    'orden',
                    'id_parada_plan_carga'
                ],
            },
        ),
        migrations.CreateModel(
            name='EntregaPlanCarga',
            fields=[
                (
                    'id_entrega_plan_carga',
                    models.AutoField(
                        primary_key=True,
                        serialize=False
                    )
                ),
                (
                    'cantidad_asignada',
                    models.PositiveIntegerField()
                ),
                (
                    'cantidad_actual',
                    models.PositiveIntegerField(default=0)
                ),
                (
                    'peso_unitario_kg',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=9
                    )
                ),
                (
                    'peso_asignado_kg',
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal('0.00'),
                        max_digits=11
                    )
                ),
                (
                    'peso_actual_kg',
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal('0.00'),
                        max_digits=11
                    )
                ),
                (
                    'detalle',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='entregas',
                        to='proyectos.detalleplancarga'
                    )
                ),
                (
                    'parada',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='entregas',
                        to='proyectos.paradaplancarga'
                    )
                ),
            ],
            options={
                'ordering': [
                    'parada__orden',
                    'detalle__producto__nombre_producto'
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='paradaplancarga',
            constraint=models.UniqueConstraint(
                fields=('plan', 'orden'),
                name='orden_unico_por_plan_carga'
            ),
        ),
        migrations.AddConstraint(
            model_name='entregaplancarga',
            constraint=models.UniqueConstraint(
                fields=('parada', 'detalle'),
                name='producto_unico_por_parada_carga'
            ),
        ),
        migrations.AddField(
            model_name='ajustecargausuario',
            name='entrega',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ajustes_usuario',
                to='proyectos.entregaplancarga'
            ),
        ),
        migrations.AddField(
            model_name='ajustecargausuario',
            name='parada',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ajustes_usuario',
                to='proyectos.paradaplancarga'
            ),
        ),
        migrations.AddField(
            model_name='ajustecargausuario',
            name='parada_nombre',
            field=models.CharField(
                blank=True,
                max_length=150
            ),
        ),
    ]
