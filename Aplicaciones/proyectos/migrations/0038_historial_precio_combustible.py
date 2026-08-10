from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0037_producto_catalogo_evidencia_entrega'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialPrecioCombustible',
            fields=[
                ('id_historial_precio', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[('EXTRA', 'EXTRA'), ('DIESEL', 'DIESEL'), ('SUPER', 'SUPER'), ('ECOPAIS', 'ECOPAIS')], max_length=20)),
                ('precio_anterior_litro', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('precio_nuevo_litro', models.DecimalField(decimal_places=4, max_digits=12)),
                ('valor_ingresado', models.DecimalField(decimal_places=4, max_digits=12)),
                ('unidad_ingresada', models.CharField(choices=[('LITRO', 'Litro'), ('GALON', 'Galón')], max_length=10)),
                ('fecha_ajuste', models.DateTimeField(auto_now_add=True)),
                ('administrador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='historial_precios_combustible', to='proyectos.usuario')),
            ],
            options={'ordering': ['-fecha_ajuste', '-id_historial_precio']},
        ),
    ]
