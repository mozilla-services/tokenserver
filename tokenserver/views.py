# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from cornice import Service

discovery = Service(name='discovery', path='/')


@discovery.get()
def _discovery(request):
    return {'sync': '1.0'}
