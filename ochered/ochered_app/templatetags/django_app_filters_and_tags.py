from django import template
from django.utils import formats
from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.translation import get_language

register = template.Library()


@register.simple_tag
def digit_beautify(value):
    src = str(value)
    if "." in src:
        out, rnd = src.split(".")
    else:
        out, rnd = src, "0"
    chunks = [out[max(i - 3, 0) : i] for i in range(len(out), 0, -3)][::-1]
    formatted_out = " ".join(chunks)

    return f"{formatted_out}.{rnd}"


@register.simple_tag
def relative_time(datetime_value):
    delta = timezone.now() - datetime_value

    if delta.days == 0 and delta.seconds < 86400:
        return timesince(datetime_value, timezone.now())
    else:
        return datetime_value.strftime("%H:%M %d.%m.%Y")


@register.filter(name="custom_cut")
def cutstom_cut(text: any, length: int) -> str:
    if len(str(text)) > length:
        return str(text)[:length] + "..."
    return str(text)




@register.simple_tag
def formatted_date(date):
    return date.strftime("%d.%m.%Y")


@register.simple_tag
def formatted_time(time):
    return time.strftime("%H:%M %d.%m.%Y ")

