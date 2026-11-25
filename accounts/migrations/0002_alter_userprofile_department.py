from django.db import migrations, models
import django.db.models.deletion


def clear_old_department_values(apps, schema_editor):
    """
    The old department field stored text values.
    Existing profiles currently contain empty strings.
    Convert those empty strings to NULL before changing
    the field into a ForeignKey.
    """
    UserProfile = apps.get_model("accounts", "UserProfile")

    UserProfile.objects.filter(
        department=""
    ).update(
        department=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("ws_departments", "0001_initial"),
    ]

    operations = [

        # Step 1:
        # Make the existing text column nullable.
        migrations.AlterField(
            model_name="userprofile",
            name="department",
            field=models.CharField(
                max_length=100,
                blank=True,
                null=True,
            ),
        ),

        # Step 2:
        # Convert old empty strings to NULL.
        migrations.RunPython(
            clear_old_department_values,
            migrations.RunPython.noop,
        ),

        # Step 3:
        # Convert the field from text to Department ForeignKey.
        migrations.AlterField(
            model_name="userprofile",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees",
                to="ws_departments.department",
            ),
        ),
    ]