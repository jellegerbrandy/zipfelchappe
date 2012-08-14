from django.db import models
from decimal import Decimal

class CurrencyField(models.DecimalField):
    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        try:
            # TODO 5 may be correct for Switzerland. What about other countries?
            return super(CurrencyField, self).to_python(value).quantize(Decimal("0.05"))
        except AttributeError:
            return None
