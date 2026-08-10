from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0035_entrega_presentacion_producto'),
    ]

    operations = [
        migrations.AddField(
            model_name='viaje',
            name='administrador_ejecutor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pruebas_ruta_ejecutadas',
                to='proyectos.usuario',
            ),
        ),
        migrations.AddField(
            model_name='viaje',
            name='carga_prueba_snapshot',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='viaje',
            name='es_prueba_administrativa',
            field=models.BooleanField(default=False),
        ),
    ]
