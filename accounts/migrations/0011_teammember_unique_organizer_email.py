from django.db import migrations, models


def dedupe_team_members(apps, schema_editor):
    TeamMember = apps.get_model('accounts', 'TeamMember')
    seen = set()
    for member in TeamMember.objects.order_by('created_at', 'id'):
        key = (member.organizer_id, member.email.lower())
        if key in seen:
            member.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_adminnotificationstate'),
    ]

    operations = [
        migrations.RunPython(dedupe_team_members, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='teammember',
            constraint=models.UniqueConstraint(
                fields=('organizer', 'email'),
                name='unique_team_member_per_organizer_email',
            ),
        ),
    ]
