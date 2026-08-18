from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0042_mejorar_catalogo_peso_presentacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductoCatalogoPersonalizado',
            fields=[
                ('id_catalogo_personalizado', models.AutoField(primary_key=True, serialize=False)),
                ('nombre_producto', models.CharField(max_length=100)),
                ('marca_producto', models.CharField(max_length=100)),
                ('precio_referencia', models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True)),
                ('contenido_unitario', models.DecimalField(decimal_places=3, max_digits=9)),
                ('unidad_contenido', models.CharField(choices=[('ML', 'ml'), ('L', 'L'), ('G', 'g'), ('KG', 'kg')], max_length=3)),
                ('activo', models.BooleanField(default=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['marca_producto', 'nombre_producto'],
            },
        ),
    ]
