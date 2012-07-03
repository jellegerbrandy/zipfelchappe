from django.contrib import admin
from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals, Q
from django.utils.translation import ugettext_lazy as _

from orderable_inlines import OrderableTabularInline

from feincms.admin import item_editor
from feincms.management.checker import check_database_schema as check_db_schema
from feincms.models import Base

from .base import CreateUpdateModel
from .fields import CurrencyField


class Project(Base):

    title = models.CharField(_('title'), max_length=100)

    slug = models.SlugField(_('slug'))

    goal = CurrencyField(_('goal'), max_digits=10, decimal_places=2,
        help_text = _('CHF you want to raise'))

    start = models.DateField(_('start'),
        help_text=_('Date the project will be online'))

    end = models.DateField(_('end'),
        help_text=_('Until when money is raised'))

    class Meta:
        verbose_name = _('project')
        verbose_name_plural = _('projects')
        get_latest_by = 'end'


    def __unicode__(self):
        return self.title

signals.post_syncdb.connect(check_db_schema(Project, __name__), weak=False)


class Reward(CreateUpdateModel):

    project = models.ForeignKey(Project, related_name='rewards')

    order = models.PositiveIntegerField(default=1)

    minimum = CurrencyField(_('minimum'), max_digits=10, decimal_places=2,
        help_text = _('How much does one have to donate to receive this?'))

    description = models.TextField(_('description'), blank=True)

    quantity = models.IntegerField(_('quantity'), blank=True, null=True,
        help_text = _('How many times can this award be give away? Leave empty \
                       to means unlimited'))


class RewardInlineAdmin(OrderableTabularInline):
    model = Reward
    extra = 1
    orderable_field = 'order'


class ProjectAdmin(item_editor.ItemEditor):
    inlines = [RewardInlineAdmin, ]
    date_hierarchy = 'end'
    list_display = ['title', 'goal']
    search_fields = ['title', 'slug']
    prepopulated_fields = {
        'slug': ('title',),
        }

    fieldset_insertion_index = 1
    fieldsets = [
        [None, {
            'fields': [
                ('title', 'slug'),
                'goal',
                ('start', 'end'),
            ]
        }],
        item_editor.FEINCMS_CONTENT_FIELDSET,
    ]