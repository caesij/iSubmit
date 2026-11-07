from functools import reduce
from operator import and_, or_

from django.db.models import Q


def all_terms_query(value, *fields):
    if not fields:
        return Q()

    return reduce(
        and_,
        (
            reduce(
                or_,
                (
                    Q(**{f'{field}__icontains': term}) for field in fields
                )
            )
            for term in (value or '').split()
        ),
        Q()
    )