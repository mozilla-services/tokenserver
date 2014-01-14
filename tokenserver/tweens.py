# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import time
import random

from pyramid.httpexceptions import HTTPException, HTTPServiceUnavailable


def set_x_timestamp_header(handler, registry):
    """Tween to set the X-Timestamp header on all responses."""

    def set_x_timestamp_header_tween(request):
        try:
            response = handler(request)
        except HTTPException, response:
            response.headers["X-Timestamp"] = str(int(time.time()))
            raise
        else:
            response.headers["X-Timestamp"] = str(int(time.time()))
            return response

    return set_x_timestamp_header_tween


def includeme(config):
    """Include all the TokenServer tweens into the given config."""
    config.add_tween("tokenserver.tweens.set_x_timestamp_header")
