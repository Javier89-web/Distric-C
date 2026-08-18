from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0040_viaje_es_plan_general'),
    ]

    operations = [
        migrations.AddField(
            model_name='historialpreciocombustible',
            name='nota',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
