from typing import List

from attr import define, field

from requests_cache.models import RichMixin


@define
class DemoModel(RichMixin):
    str_attr: str = field(default=None)
    int_attr: int = field(default=None)
    list_attr: List[str] = field(factory=list)
    _private_attr: bool = field(default=False, repr=False)


def test_rich_mixin():
    """Test that RichMixin.__rich_repr__ informs rich about all public attributes, current values,
    and defaults
    """
    model = DemoModel(str_attr='str', int_attr=1, list_attr=['a', 'b'])
    repr_tokens = list(model.__rich_repr__())
    assert repr_tokens == [
        ('str_attr', 'str', None),
        ('int_attr', 1, None),
        ('list_attr', ['a', 'b'], []),
    ]


def test_repr():
    """Test that regular __repr__ excludes default values"""
    assert repr(DemoModel() == 'DemoModel()')
    assert repr(DemoModel(str_attr='str') == "DemoModel(str_attr='str')")
