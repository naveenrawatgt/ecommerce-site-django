# Generated by Django 3.0 on 2021-01-15 17:41

from django.db import migrations
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_order_billing_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billingaddress',
            name='country',
            field=django_countries.fields.CountryField(max_length=2),
        ),
    ]
