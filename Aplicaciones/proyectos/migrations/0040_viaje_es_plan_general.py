from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0039_reportepdfviaje'),
    ]

    operations = [
        migrations.AddField(
            model_name='viaje',
            name='es_plan_general',
            field=models.BooleanField(default=False),
        ),
    ]
