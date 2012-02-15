# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import json

from cornice import Service

discovery = Service(name='discovery', path='/')


@discovery.get()
def _discovery(request):
    discovery = os.path.join(os.path.dirname(__file__), 'discovery.json')

    with open(discovery) as f:
        return json.loads(f.read())
