from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0034_viajes_predictivos_tramos_gps"),
    ]

    operations = [
        migrations.AddField(
            model_name="entregatramoviaje",
            name="marca_producto",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="entregatramoviaje",
            name="presentacion_producto",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
