from cornice import Service


discovery = Service(name='discovery', path='/')


@discovery.get()
def _discovery(request):
    return {'sync': '1.0'}

