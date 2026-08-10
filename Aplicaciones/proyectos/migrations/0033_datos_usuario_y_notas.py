from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0032_paradas_entregas_confirmacion_carga'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='cedula_usuario',
            field=models.CharField(
                blank=True,
                max_length=10,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='telefono_usuario',
            field=models.CharField(
                blank=True,
                max_length=15,
                null=True,
            ),
        ),
        migrations.RenameField(
            model_name='productocarga',
            old_name='descripcion_producto',
            new_name='nota_producto',
        ),
        migrations.RenameField(
            model_name='plancarga',
            old_name='observaciones',
            new_name='notas',
        ),
    ]
