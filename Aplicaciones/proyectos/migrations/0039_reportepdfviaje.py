from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0038_historial_precio_combustible'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportePDFViaje',
            fields=[
                ('id_reporte_pdf', models.AutoField(primary_key=True, serialize=False)),
                ('unidad_combustible', models.CharField(choices=[('LITROS', 'LITROS'), ('GALONES', 'GALONES')], default='LITROS', max_length=10)),
                ('nombre_archivo', models.CharField(max_length=255)),
                ('cloudinary_public_id', models.CharField(max_length=500)),
                ('cloudinary_url', models.URLField(max_length=1000)),
                ('tamanio_bytes', models.PositiveBigIntegerField(default=0)),
                ('fecha_respaldo', models.DateTimeField(auto_now=True)),
                ('viaje', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='respaldos_pdf', to='proyectos.viaje')),
            ],
            options={
                'ordering': ['-fecha_respaldo'],
            },
        ),
        migrations.AddConstraint(
            model_name='reportepdfviaje',
            constraint=models.UniqueConstraint(fields=('viaje', 'unidad_combustible'), name='uq_reporte_pdf_viaje_unidad'),
        ),
    ]
