from django.http import HttpRequest, HttpResponseRedirect


def public_root_redirect(request: HttpRequest) -> HttpResponseRedirect:
    return HttpResponseRedirect("/public/")
