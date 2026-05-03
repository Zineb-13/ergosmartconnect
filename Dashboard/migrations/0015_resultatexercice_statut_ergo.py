from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0014_delete_notificationergo'),
    ]

    operations = [
        migrations.AddField(
            model_name='resultatexercice',
            name='statut_ergo',
            field=models.CharField(
                choices=[('pending', 'En attente'), ('validated', 'Validé'), ('refused', 'Refusé')],
                default='pending',
                max_length=20,
                verbose_name='Statut ergo',
            ),
        ),
    ]
