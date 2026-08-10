from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0030_ajustes_carga_usuario'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehiculo',
            name='foto_vehiculo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='vehiculos/'
            ),
        ),
    ]
