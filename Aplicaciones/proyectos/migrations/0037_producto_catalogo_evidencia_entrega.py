from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0036_viaje_pruebas_administrativas'),
    ]

    operations = [
        migrations.AddField(
            model_name='productocarga',
            name='codigo_catalogo',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='productocarga',
            name='precio_referencia',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='tramoviaje',
            name='evidencia_entrega',
            field=models.ImageField(blank=True, null=True, upload_to='evidencias_entrega/%Y/%m/'),
        ),
    ]
